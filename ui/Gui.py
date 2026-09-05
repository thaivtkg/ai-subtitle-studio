import copy
import os
import re
import sys
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.artifacts.artifact_store import ArtifactStore
from core.media_import.media_import_service import MediaImportService
from core.project.transcription_context import TranscriptionContext
from core.queue_manager import QueueManager
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import RecoveryContext, RecoveryWorkingState
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker
from core.runtime.runtime_paths import RuntimePaths
from core.runtime.single_instance_guard import IpcAction, IpcRequest
from core.services.project_service import ProjectService
from core.services.workspace_service import WorkspaceService
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.selection_controller import SubtitleSelectionController
from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from core.timing.timing_batch_service import TimingBatchService
from core.help.help_center_controller import HelpCenterController
from core.tutorial.catalog import TourCatalog
from core.tutorial.environment import TourEnvironment
from core.tutorial.progress_store import TourProgressStore
from core.tutorial.tour_engine import TourEngine
from core.video_metadata import MetadataWorker
from player.video_player import VideoPlayerWidget
from ui.animations.animation_types import SubtitleAppearMode, SubtitleDisappearMode
from ui.animations.subtitle_animation_controller import SubtitleTextEffect
from ui.components.animated_stack import AnimatedStack
from ui.components.transcription_context_panel import TranscriptionContextPanel
from ui.dialogs.media_import_dialog import MediaImportDialog
from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.pages.dashboard_page import DashboardPage
from ui.pages.draft_center_page import DraftCenterPage
from ui.pages.export_center_page import ExportCenterPage
from ui.pages.help_center_page import HelpCenterPage
from ui.help.shortcut_provider import RuntimeShortcutProvider
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.dialog_observer import DialogLifecycleObserver
from ui.tutorial.interaction_observer import InteractionObserverAdapter
from ui.tutorial.navigation_adapter import MainWindowRouter
from ui.tutorial.spotlight_layer import SpotlightLayerAdapter
from ui.pages.settings_page import SettingsCenterPage
from ui.queue_widget import QueueWidget
from ui.SubEditor import SubtitleEditorWidget
from ui.subtitle_generation_panel import SubtitleGenerationPanel
from ui.subtitle_inspector_panel import SubtitleInspectorPanel
from ui.theme import Theme
from ui.toast import Toast
from utils import load_settings, save_settings
from workers.TaskQueue import HardsubWorker


class StreamRedirector(QObject):
    text_written = Signal(str)
    
    def __init__(self, stream):
        super().__init__()
        self.stream = stream

    def write(self, text):
        if text.strip():
            self.text_written.emit(text.strip())

    def flush(self):
        pass

class MainWindow(QMainWindow):
    # [FIX MẠNG] Khai báo Signal giao tiếp xuyên luồng (Cross-thread) an toàn
    waveform_ready_signal = Signal(str, int, object)

    def __init__(self, revision_tracker=None, recovery_manager=None, undo_manager=None,
                 parent=None, project_service=None, media_import_service=None):
        super().__init__(parent)

        # Lắng nghe Signal vẽ sóng âm từ luồng phụ gửi lên
        self.waveform_ready_signal.connect(self._on_waveform_ready_slot)

        # --- KHỞI TẠO HỆ THỐNG PROJECT (SPRINT 7) ---
        self.artifact_store = ArtifactStore()
        self.undo_manager = undo_manager or GlobalUndoManager(self)
        self.global_undo_manager = self.undo_manager
        self.revision_tracker = revision_tracker or RevisionTracker(self.undo_manager, self)
        self.project_service = project_service or ProjectService(self.artifact_store)
        if project_service is not None:
            self.artifact_store = getattr(project_service, "artifact_store", self.artifact_store)
        self.project_service.revision_tracker = self.revision_tracker
        self.media_import_service = media_import_service or MediaImportService()
        self.recovery_manager = recovery_manager or RecoveryManager(
            RuntimePaths.get_recovery_sessions_dir(),
            RuntimePaths.get_recovery_quarantine_dir(),
            self.revision_tracker,
            AtomicSnapshotStore(),
            RecoveryValidator(),
            self,
        )
        self.workspace_service = WorkspaceService(self, self.project_service)
        self.revision_tracker.dirty_changed.connect(self._update_window_title_dirty_marker)
        self.revision_tracker.clean_point_reached.connect(
            self.recovery_manager.invalidate_snapshot_at_clean_point
        )
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30_000)
        self.autosave_timer.timeout.connect(self._on_autosave_timeout)
        self.autosave_timer.start()
        self.selection_controller = SubtitleSelectionController(self)

        # --- [SPRINT 9] ROBUST SUBTITLE GENERATION ---
        from core.subtitle_generation.faster_whisper_service import FasterWhisperService
        from core.subtitle_generation.generation_service import (
            SubtitleGenerationService,
        )
        self.subtitle_whisper_service = FasterWhisperService()
        self.subtitle_generation_service = SubtitleGenerationService(
            self.subtitle_whisper_service, self.project_service
        )
        self.subtitle_generation_service.on_batch_complete = self._on_generation_batch_sync
        self.timing_service = TimingBatchService(self.project_service)

        # Phím tắt Dự án (Gắn cờ ApplicationShortcut để chống mất Focus)
        self.shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self.shortcut_new.setContext(Qt.ApplicationShortcut)
        self.shortcut_new.activated.connect(self.action_new_project)

        self.action_new_from_url = QAction("New from URL...", self)
        self.action_new_from_url.triggered.connect(self._on_new_from_url)
        self.action_add_url_to_queue = QAction("Add URL to Queue...", self)
        self.action_add_url_to_queue.triggered.connect(self._on_add_url_to_queue)
        
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.setContext(Qt.ApplicationShortcut)
        self.shortcut_open.activated.connect(self.action_open_project)

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.setContext(Qt.ApplicationShortcut)
        self.shortcut_save.activated.connect(self.action_save_project)
        self.shortcut_export = QShortcut(QKeySequence("Ctrl+Shift+E"), self)
        self.shortcut_export.setContext(Qt.ApplicationShortcut)
        self.shortcut_export.activated.connect(self._trigger_export_softsub)

        self.setWindowTitle("AI Subtitle Studio")
        
        self.setMinimumSize(1280, 720)
        self.resize(1366, 768)
        self.setDockOptions(
            QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks
        )
        self.center_on_screen()
        self.setStyleSheet(Theme.get_global_stylesheet())
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.old_pos = QPoint()
        self._is_dragging = False

        self.queue_mgr = QueueManager()
        self._queue_project_dirs = {}
        self.queue_mgr.queue_updated.connect(self.on_queue_updated)
        self.queue_mgr.active_changed.connect(
            lambda vid: self.queue_ui.sync_with_manager(self.queue_mgr.get_items(), vid) if hasattr(self, 'queue_ui') else None
        )
        self.queue_mgr.item_removed.connect(self.on_queue_item_removed_handler)
        self.setAcceptDrops(True)

        root_widget = QWidget()
        root_widget.setMinimumSize(800, 600)
        root_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCentralWidget(root_widget)
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ========================================================
        # 1. SIDEBAR NAVIGATION
        # ========================================================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame")
        self.sidebar.setFixedWidth(230)
        self.sidebar.setStyleSheet(f"#SidebarFrame {{ background-color: {Theme.SURFACE}; border-right: 1px solid {Theme.BORDER}; }}")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(4)

        logo_lbl = QLabel("✨ AI Subtitle Studio")
        logo_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; padding: 4px 4px 10px 4px; border: none;")
        sidebar_layout.addWidget(logo_lbl)

        # Đổi tên nhóm và trỏ sự kiện về các hàm Project (Sprint 7)
        sidebar_layout.addWidget(QLabel("QUẢN LÝ DỰ ÁN", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 4px;"))
        
        # Nút Tạo Dự Án 
        btn_new_project = self.create_side_action_button("✨  Tạo Dự Án Mới", self.action_new_project)
        btn_new_project.setStyleSheet(f"QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.CYAN}; border-radius: 6px; color: {Theme.CYAN}; text-align: left; padding-left: 10px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; }}")
        sidebar_layout.addWidget(btn_new_project)
        sidebar_layout.addWidget(self.create_side_action_button("🌐  New from URL...", self._on_new_from_url))
        sidebar_layout.addWidget(self.create_side_action_button("➕  Add URL to Queue...", self._on_add_url_to_queue))
        
        # Nút Mở Dự Án 
        sidebar_layout.addWidget(self.create_side_action_button("📂  Mở Dự Án...", self.action_open_project))
        
        # Nút Lưu Dự Án
        sidebar_layout.addWidget(self.create_side_action_button("💾  Lưu Dự Án", self.action_save_project))
        
        # Nút Clear Queue
        sidebar_layout.addWidget(self.create_side_action_button("🗑  Clear Queue", self.clear_files))

        sidebar_layout.addWidget(QLabel("WORKFLOW SURFACES", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 8px;"))
        self.nav_btns = {}
        sidebar_layout.addWidget(self.create_nav_button("📊  Dashboard", 0))
        sidebar_layout.addWidget(self.create_nav_button("🎬  Video Workspace", 1))
        sidebar_layout.addWidget(self.create_nav_button("📝  Subtitle Editor", 2))
        sidebar_layout.addWidget(self.create_nav_button("📋  Queue & Output", 3))
        sidebar_layout.addWidget(self.create_nav_button("📦  Draft Center", 4))
        sidebar_layout.addWidget(self.create_nav_button("🚀  Export Center", 5))

        sidebar_layout.addStretch()
        sidebar_layout.addWidget(QLabel("HỆ THỐNG", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none;"))
        sidebar_layout.addWidget(self.create_nav_button("⚙  Settings Center", 6))
        sidebar_layout.addWidget(self.create_nav_button("❓  Help Center", 7))
        # Thêm nút Model Manager
        sidebar_layout.addWidget(self.create_side_action_button("📦  Model Manager", self.action_open_model_manager))

        root_layout.addWidget(self.sidebar)

        # --- BỔ SUNG: KHỞI TẠO SIDEBAR INDICATOR ---
        self.sidebar_indicator = QFrame(self.sidebar)
        self.sidebar_indicator.setFixedSize(4, 20) 
        self.sidebar_indicator.setStyleSheet(f"background-color: {Theme.CYAN}; border-radius: 2px;")
        
        self.indicator_anim = QPropertyAnimation(self.sidebar_indicator, b"pos")
        self.indicator_anim.setDuration(160)
        self.indicator_anim.setEasingCurve(QEasingCurve.OutCubic)

        # ========================================================
        # 2. RIGHT WORKSPACE AREA
        # ========================================================
        right_area = QWidget()
        right_area.setObjectName("RightArea")
        right_area.setStyleSheet(f"#RightArea {{ background-color: {Theme.BG_APP}; }}")
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopbarFrame")
        topbar.setFixedHeight(42)
        topbar.setStyleSheet(f"#TopbarFrame {{ background-color: {Theme.BG_APP}; border-bottom: 1px solid {Theme.BORDER}; }}")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(14, 0, 10, 0)

        self.lbl_page_title = QLabel("Dashboard")
        self.lbl_page_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; border: none;")
        topbar_layout.addWidget(self.lbl_page_title)
        topbar_layout.addStretch()

        btn_minimize = QPushButton("—")
        btn_minimize.setToolTip("Thu nhỏ cửa sổ")
        btn_minimize.setFixedSize(28, 24)
        btn_minimize.setStyleSheet(f"QPushButton {{ background: transparent; color: {Theme.TEXT_SECONDARY}; border: none; border-radius: 4px; font-weight: bold; }} QPushButton:hover {{ background: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}")
        btn_minimize.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setToolTip("Đóng ứng dụng")
        btn_close.setFixedSize(28, 24)
        btn_close.setStyleSheet(f"QPushButton {{ background: transparent; color: {Theme.DANGER}; border: none; border-radius: 4px; font-weight: bold; }} QPushButton:hover {{ background: {Theme.DANGER}; color: #FFFFFF; }}")
        btn_close.clicked.connect(self.close)

        topbar_layout.addWidget(btn_minimize)
        topbar_layout.addWidget(btn_close)
        right_layout.addWidget(topbar)

        # ========================================================
        # 3. STACKED WIDGET (Sửa lỗi chia sẻ Widget)
        # ========================================================
        self.stack = AnimatedStack()

        # Page 0: Dashboard
        self.page_dashboard = DashboardPage()
        self.page_dashboard.navigate_requested.connect(self.switch_page)
        self.stack.addWidget(self.page_dashboard)

        # ========================================================
        # PAGE 1: VIDEO WORKSPACE (DAW-STANDARD 3-TIER LAYOUT)
        # ========================================================
        self.page_workspace = QWidget()
        ws_layout = QVBoxLayout(self.page_workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0) # Gỡ viền thừa để tối đa hóa không gian
        ws_layout.setSpacing(0)

        # Splitter dọc: top workspace (Editor + Video) trên Timeline
        self.workspace_vertical_splitter = QSplitter(Qt.Vertical)
        self.workspace_vertical_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; height: 2px; }}")
        self.work_splitter = self.workspace_vertical_splitter

        # --- TOP WORKSPACE: EDITOR 68% / VIDEO 32% ---
        self.top_horizontal_splitter = QSplitter(Qt.Horizontal)
        self.top_horizontal_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; width: 2px; }}")
        self.top_splitter = self.top_horizontal_splitter
        self.sub_editor = SubtitleEditorWidget()
        self.sub_editor.project_service = self.project_service
        self.sub_editor.undo_manager = self.undo_manager
        self.sub_editor.selection_controller = self.selection_controller
        self.selection_controller.selection_changed.connect(self.sub_editor.sync_selection)
        self.undo_manager.state_changed.connect(self.sub_editor.render_page)
        self.undo_manager.state_changed.connect(self.sub_editor.update_draft_progress)
        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(200)
        self.top_horizontal_splitter.addWidget(self.sub_editor)
        self.top_horizontal_splitter.addWidget(self.video_player)
        self.top_horizontal_splitter.setStretchFactor(0, 56)
        self.top_horizontal_splitter.setStretchFactor(1, 44)
        self.top_horizontal_splitter.setSizes([560, 440])

        self.sub_editor.seek_requested.connect(self.video_player.set_position)
        self.video_player.sub_controller.subtitle_cleared.connect(self.sub_editor.clear_highlight)
        self.video_player.sub_controller.subtitle_changed.connect(
            lambda stt, start, text: self.sub_editor.sync_playback_highlight(int(stt) - 1)
        )
        self.sub_editor.live_edit_applied.connect(self.video_player.sub_controller.update_live_data)
        self.sub_editor.live_edit_applied.connect(lambda *args: self.project_service.mark_dirty() if getattr(self, 'project_service', None) else None)
        self._setup_global_shortcuts()

        self.workspace_vertical_splitter.addWidget(self.top_horizontal_splitter)

        # Live log is hosted in the generation dock tab.
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái...")

        # --- [SPRINT 9] RIGHT DOCK: SUBTITLE GENERATION + LIVE LOG ---
        self.generation_panel = SubtitleGenerationPanel(
            self.subtitle_generation_service, self
        )
        self.generation_panel.timing_start_requested.connect(
            self._start_timing_draft
        )
        self.generation_panel.timing_resume_requested.connect(
            self._resume_timing_draft
        )
        self.generation_panel.timing_cancel_requested.connect(
            self.timing_service.cancel_timing
        )
        self.generation_panel.request_context_edit.connect(self._show_context_inspector)
        self.timing_service.progress_signal.connect(self._on_timing_progress)
        self.timing_service.log_signal.connect(self._on_timing_log)
        self.timing_service.batch_completed_signal.connect(
            self._on_timing_batch_completed
        )
        self.timing_service.state_changed_signal.connect(
            self._on_timing_state_changed
        )
        self.timing_service.error_signal.connect(self._on_timing_error)
        self._restore_panel_callbacks()
        self.generation_dock = QDockWidget("AI Workspace", self)
        self.generation_dock.setObjectName("SubtitleGenerationDock")
        self.generation_dock.setAllowedAreas(
            Qt.RightDockWidgetArea
        )
        self.generation_dock.setFeatures(
            QDockWidget.DockWidgetMovable
        )
        self.generation_dock.setMinimumWidth(350)
        self.generation_dock.setMaximumWidth(390)
        self.generation_dock.setStyleSheet(f"""
            QDockWidget {{
                color: {Theme.TEXT_PRIMARY};
                font-weight: bold;
            }}
            QDockWidget::title {{
                background: {Theme.SURFACE};
                padding: 6px 10px;
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)
        dock_tabs = QTabWidget()
        dock_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border-top: 1px solid {Theme.BORDER};
                background: transparent;
            }}
            QTabBar::tab {{
                background: {Theme.BG_APP};
                color: {Theme.TEXT_MUTED};
                padding: 8px 16px;
                border: none;
                margin: 0px;
                min-height: 22px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {Theme.PRIMARY_PURPLE};
                color: #FFFFFF;
                font-weight: bold;
                margin: 0px;
            }}
            QTabBar::tab:hover:!selected {{
                background: {Theme.SURFACE_SOFT};
            }}
            QTabBar::scroller {{
                width: 28px;
            }}
            QTabBar QToolButton {{
                background: {Theme.SURFACE};
                border: none;
                color: {Theme.TEXT_PRIMARY};
            }}
            QTabBar QToolButton:hover {{
                background: {Theme.SURFACE_SOFT};
            }}
        """)
        dock_tabs.addTab(self.generation_panel, "✨ Generate")
        self.context_panel = TranscriptionContextPanel(self)
        self.context_panel.context_committed.connect(
            self.on_transcription_context_committed
        )
        dock_tabs.addTab(self.context_panel, "📝 Context")
        self.inspector_panel = SubtitleInspectorPanel()
        self.subtitle_inspector = self.inspector_panel
        dock_tabs.addTab(self.inspector_panel, "🎨 Style")
        dock_tabs.addTab(self.log_box, "📜 Log")
        self.dock_tabs = dock_tabs
        self.inspector_panel.preview_toggled.connect(self._on_preview_toggled)
        self.inspector_panel.style_changed.connect(self._on_subtitle_style_changed)
        self.generation_dock.setWidget(dock_tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, self.generation_dock)

        self.btn_drawer_toggle = QPushButton("›", self)
        self.btn_drawer_toggle.setFixedSize(20, 56)
        self.btn_drawer_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_drawer_toggle.setToolTip("Ẩn AI Workspace")
        self.btn_drawer_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE_ELEVATED};
                border: 1px solid {Theme.BORDER};
                border-right: none;
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
                color: {Theme.TEXT_MUTED};
                font-weight: bold;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.TEXT_PRIMARY};
            }}
        """)
        self.btn_drawer_toggle.clicked.connect(self._toggle_ai_drawer)
        self.generation_dock.visibilityChanged.connect(self._sync_drawer_toggle_state)
        self._drawer_target_width = 350
        self.drawer_anim = QVariantAnimation(self)
        self.drawer_anim.setDuration(250)
        self.drawer_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.drawer_anim.valueChanged.connect(self._on_drawer_anim_step)
        self.drawer_anim.finished.connect(self._on_drawer_anim_finished)
        self.centralWidget().installEventFilter(self)
        self._update_drawer_handle_position()

        # --- TẦNG 3: TIMELINE & WAVEFORM ---
        from core.timeline.timeline_controller import TimelineController
        from core.timeline.timeline_data_provider import TimelineDataProvider
        from core.timeline.timeline_integration import TimelineVideoSync
        from ui.timeline.timeline_widget import TimelineWidget

        self.timeline_widget = TimelineWidget()
        self.timeline_widget.setMinimumHeight(160) # Timeline nay đã nằm dưới cùng, chiếm ưu thế
        self.workspace_vertical_splitter.addWidget(self.timeline_widget)

        self.timeline_data_provider = TimelineDataProvider()
        self.timeline_controller = TimelineController(
            self.project_service, self.timeline_widget, self.timeline_data_provider,
            undo_manager=self.undo_manager, selection_controller=self.selection_controller,
        )
        self.undo_manager.state_changed.connect(self.timeline_controller._refresh_ui)
        self.video_sync = TimelineVideoSync(self.video_player, self.timeline_widget, self.timeline_controller.state_manager)
        
        # Liên kết Cầu đồng bộ (Click Table -> Bôi đen Timeline)
        self.sub_editor.seek_requested.connect(self.timeline_controller.sync_from_editor)

        # Chốt tỷ lệ: top workspace 68% / timeline 32%
        self.workspace_vertical_splitter.setStretchFactor(0, 68)
        self.workspace_vertical_splitter.setStretchFactor(1, 32)
        self.workspace_vertical_splitter.setSizes([680, 320])
        ws_layout.addWidget(self.workspace_vertical_splitter)
        
        self.stack.addWidget(self.page_workspace)

        # Page 3 (Index 2): Queue & Output
        self.page_queue = QWidget()
        queue_layout = QVBoxLayout(self.page_queue)
        queue_layout.setContentsMargins(8, 8, 8, 8)
        self.queue_ui = QueueWidget()
        self.queue_ui.item_clicked.connect(self.on_queue_item_clicked)
        self.queue_ui.item_removed.connect(self.queue_mgr.remove_video)
        queue_layout.addWidget(self.queue_ui)
        self.stack.addWidget(self.page_queue)

        # Page 4 (Index 3): Draft Center
        self.page_drafts = DraftCenterPage()
        self.page_drafts.open_draft_requested.connect(self._load_draft_from_center)

        self.page_drafts.continue_draft_requested.connect(self._continue_draft_from_center)

        self.stack.addWidget(self.page_drafts)

        # Page 5 (Index 4): Export Center
        self.page_export = ExportCenterPage()
        self.page_export.export_srt_requested.connect(self._trigger_export_softsub)
        self.page_export.burn_hardsub_requested.connect(self._trigger_export_hardsub)
        self.stack.addWidget(self.page_export)

        # Page 6 (Index 5): Settings Center
        self.page_settings = SettingsCenterPage()
        self.page_settings.motion_preset_combo.currentIndexChanged.connect(self.on_motion_preset_changed)
        self.page_settings.appear_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.page_settings.disappear_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.page_settings.text_effect_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.stack.addWidget(self.page_settings)

        # Page 7 (Index 6): Help Center
        self.tour_catalog = TourCatalog(RuntimePaths.get_resources_dir() / "tutorials")
        self.tour_progress_store = TourProgressStore(RuntimePaths.get_tutorial_progress_file())
        self.tour_environment = TourEnvironment(self._check_tour_precondition)
        self.shortcut_provider = RuntimeShortcutProvider(self)
        self.tour_anchor_registry = AnchorRegistry()
        self.tour_dialog_observer = DialogLifecycleObserver(self)
        self.tour_interaction_observer = InteractionObserverAdapter(
            self.tour_anchor_registry, self.tour_dialog_observer, self
        )
        self.tour_navigation = MainWindowRouter(self, self)
        self.tour_spotlight = SpotlightLayerAdapter(self.tour_anchor_registry, self)
        self.tour_engine = TourEngine(
            self.tour_catalog,
            self.tour_anchor_registry,
            self.tour_navigation,
            self.tour_interaction_observer,
            self.tour_spotlight,
            self.tour_dialog_observer,
            self.tour_progress_store,
            self.tour_environment,
            self,
        )
        self.help_controller = HelpCenterController(
            self.tour_catalog,
            self.tour_progress_store,
            self.tour_environment,
            start_tour_fn=self._start_tour_from_help,
            shortcut_provider=self.shortcut_provider,
        )
        self.page_help = HelpCenterPage(self.help_controller, self.shortcut_provider, self)
        self.stack.addWidget(self.page_help)

        right_layout.addWidget(self.stack, stretch=1)

        # ========================================================
        # 4. COMPACT GLOBAL BOTTOM BAR 
        # ========================================================
        self.bottom_frame = QFrame()
        self.bottom_frame.setObjectName("BottomFrame")
        self.bottom_frame.setMinimumHeight(96)
        self.bottom_frame.setStyleSheet(f"#BottomFrame {{ background-color: {Theme.SURFACE}; border-top: 1px solid {Theme.BORDER}; }}")
        bottom_layout = QVBoxLayout(self.bottom_frame) # <-- Sửa ở đây
        bottom_layout.setContentsMargins(14, 10, 14, 10)
        bottom_layout.setSpacing(10)

        out_row = QHBoxLayout()
        lbl_out = QLabel("📁 Output:")
        lbl_out.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold; font-size: 11px;")
        
        self.out_input = QLineEdit()
        self.out_input.setMinimumHeight(30)
        self.out_input.setPlaceholderText("Thư mục lưu kết quả...")
        
        out_btn = QPushButton("Browse...")
        out_btn.setMinimumHeight(30)
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self.select_output_dir)

        out_row.addWidget(lbl_out)
        out_row.addWidget(self.out_input, stretch=1)
        out_row.addWidget(out_btn)
        bottom_layout.addLayout(out_row)

        prog_action_row = QHBoxLayout()
        prog_action_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(12)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"QProgressBar {{ background: {Theme.BG_APP}; border: none; border-radius: 4px; }} QProgressBar::chunk {{ background: {Theme.PRIMARY_GRADIENT}; border-radius: 4px; }}")

        self.progress_anim = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_anim.setDuration(400)

        self.lbl_speed_eta = QLabel("Speed: 0.0x | ETA: --")
        self.lbl_speed_eta.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; font-weight: bold;")

        self.start_btn = QPushButton("▶ Start Queue")
        self.start_btn.setMinimumHeight(32)
        self.start_btn.setObjectName("btn_primary")
        self.start_btn.clicked.connect(self.start_processing)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.setObjectName("btn_danger")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setMinimumHeight(32)
        open_folder_btn.setObjectName("btn_secondary")
        open_folder_btn.clicked.connect(self.open_output_folder)

        prog_action_row.addWidget(self.progress_bar, stretch=3)
        prog_action_row.addWidget(self.lbl_speed_eta, stretch=1)
        prog_action_row.addWidget(self.start_btn)
        prog_action_row.addWidget(self.cancel_btn)
        prog_action_row.addWidget(open_folder_btn)

        bottom_layout.addLayout(prog_action_row)
        right_layout.addWidget(self.bottom_frame)
        # Keep the central workspace expanding when the drawer is closed.
        root_layout.addWidget(right_area, stretch=1)

        self.stdout_redirector = StreamRedirector(sys.stdout)
        self.stdout_redirector.text_written.connect(self.append_log)
        sys.stdout = self.stdout_redirector

        self.stderr_redirector = StreamRedirector(sys.stderr)
        self.stderr_redirector.text_written.connect(self.append_log)
        sys.stderr = self.stderr_redirector

        # 5. Initialization
        self.switch_page(0)
        self.on_queue_updated()
        self.update_hardware_info()
        self.update_cpu_usage()
        self.apply_saved_settings()

        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_hardware_info)
        self.stats_timer.timeout.connect(self.update_cpu_usage)
        self.stats_timer.start(1000)
        self.inspector_panel.emit_current_style()

    # --- HÀM THỰC THI SIGNAL AN TOÀN TRÊN MAIN THREAD ---
    @Slot(dict)
    def _on_subtitle_style_changed(self, style: dict):
        """Adapt inspector's public style schema to the overlay renderer."""
        position = {"top": "Top", "center": "Middle", "bottom": "Bottom"}.get(
            str(style.get("position", "bottom")).lower(), "Bottom"
        )
        self.video_player.subtitle_overlay.update_style(
            family=style.get("font_name", style.get("family")),
            size=style.get("font_size", style.get("size")),
            color=style.get("font_color", style.get("color")),
            out_color=style.get("outline_color", style.get("out_color")),
            out_width=style.get("outline_width", style.get("out_width")),
            position=position,
        )

    # Backwards-compatible name for callers from the first refactor pass.
    _apply_subtitle_style = _on_subtitle_style_changed

    @Slot(bool)
    def _on_preview_toggled(self, is_visible: bool):
        """Toggle overlay visibility without changing subtitle controller state."""
        overlay = getattr(self.video_player, "subtitle_overlay", None)
        if overlay is not None:
            overlay.setVisible(bool(is_visible))
        controller = getattr(self.video_player, "sub_controller", None)
        if controller is not None and hasattr(controller, "toggle_preview"):
            controller.toggle_preview(bool(is_visible))

    def _on_waveform_ready_slot(self, req_vid_path, duration_ms, peaks):
        if req_vid_path != self.queue_mgr.active_vid:
            print(f"[DEBUG-WAVEFORM] Bỏ qua kết quả cũ của worker do người dùng đã chuyển video: {req_vid_path}")
            return

        try:
            self.generation_panel.set_video_duration(duration_ms)
            # 3. [FIX REVIEW 1] Nạp Data Provider SAU KHI cả SRT và Sóng âm đã sẵn sàng trên Main Thread
            self.timeline_data_provider.load_runtime_data(self.sub_editor.all_segments, duration_ms)

            self.timeline_widget.load_project_data(
                duration_ms,
                self.timeline_data_provider.get_all_segments(),
                peaks
            )
            print("[DEBUG-WAVEFORM] 7. Vẽ Timeline UI thành công!")
        except RuntimeError as e:
            print(f"[DEBUG-WAVEFORM] ❌ LỖI KHI VẼ UI: {e}")

    def center_on_screen(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.left() + (screen_geo.width() - self.width()) // 2
        y = screen_geo.top() + (screen_geo.height() - self.height()) // 2
        self.move(x, y)

    def _toggle_playback_shortcut(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QTextEdit)):
            return
        if hasattr(self.video_player, "toggle_playback"):
            self.video_player.toggle_playback()

    def _setup_global_shortcuts(self):
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_manager.undo)
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.shortcut_redo.activated.connect(self.undo_manager.redo)
        self.shortcut_merge = QShortcut(QKeySequence("Ctrl+M"), self)
        self.shortcut_merge.activated.connect(self.sub_editor.trigger_merge)
        self.shortcut_split = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.shortcut_split.activated.connect(
            lambda: self.sub_editor.trigger_split(self.video_player.get_current_time_ms())
        )
        self.shortcut_help = QShortcut(QKeySequence("F1"), self)
        self.shortcut_help.setContext(Qt.ApplicationShortcut)
        self.shortcut_help.activated.connect(lambda: self.switch_page(7))
        QApplication.instance().installEventFilter(self)

    @Slot()
    def _toggle_ai_drawer(self):
        if self.drawer_anim.state() == QAbstractAnimation.Running:
            return
        if self.generation_dock.isVisible():
            self._drawer_target_width = max(350, self.generation_dock.width())
            self.drawer_anim.setStartValue(self._drawer_target_width)
            self.drawer_anim.setEndValue(0)
            self.btn_drawer_toggle.setText("‹")
            self.btn_drawer_toggle.setToolTip("Hiện AI Workspace")
        else:
            # Set the collapsed geometry before showing to prevent a one-frame flash.
            self.generation_dock.setMinimumWidth(0)
            self.generation_dock.setMaximumWidth(0)
            self.generation_dock.show()
            self.drawer_anim.setStartValue(0)
            self.drawer_anim.setEndValue(self._drawer_target_width)
            self.btn_drawer_toggle.setText("›")
            self.btn_drawer_toggle.setToolTip("Ẩn AI Workspace")
        self.drawer_anim.start()

    @Slot(object)
    def _on_drawer_anim_step(self, current_width):
        width = max(0, int(current_width))
        self.generation_dock.setMinimumWidth(width)
        self.generation_dock.setMaximumWidth(width)
        self._update_drawer_handle_position()

    @Slot()
    def _on_drawer_anim_finished(self):
        if self.drawer_anim.endValue() == 0:
            self.generation_dock.hide()
        self.generation_dock.setMinimumWidth(350)
        self.generation_dock.setMaximumWidth(390)
        self._update_drawer_handle_position()

    @Slot(bool)
    def _sync_drawer_toggle_state(self, is_visible: bool):
        self.btn_drawer_toggle.setText("›" if is_visible else "‹")
        self.btn_drawer_toggle.setToolTip(
            "Ẩn AI Workspace" if is_visible else "Hiện AI Workspace"
        )
        self._update_drawer_handle_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_drawer_handle_position()

    def _update_drawer_handle_position(self):
        if not hasattr(self, "btn_drawer_toggle"):
            return
        y = max(0, (self.height() - self.btn_drawer_toggle.height()) // 2)
        if self.generation_dock.isVisible():
            x = self.centralWidget().width() - self.btn_drawer_toggle.width()
        else:
            x = self.width() - self.btn_drawer_toggle.width()
        self.btn_drawer_toggle.move(max(0, x), y)
        self.btn_drawer_toggle.raise_()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and self.isActiveWindow():
            focus_widget = QApplication.focusWidget()
            is_typing = isinstance(focus_widget, (QTextEdit, QLineEdit))
            if event.key() == Qt.Key_Space and not is_typing:
                self.video_player.toggle_playback()
                return True
            if event.key() == Qt.Key_Delete and not is_typing:
                self.sub_editor.trigger_delete()
                return True
        if obj == self.centralWidget() and event.type() == QEvent.Resize:
            self._update_drawer_handle_position()
        return super().eventFilter(obj, event)

    def create_nav_button(self, text, page_index):
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {Theme.TEXT_SECONDARY}; text-align: left; padding-left: 10px; border-radius: 6px; font-weight: 600; font-size: 12px; border: none; }} QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}")
        btn.clicked.connect(lambda: self.switch_page(page_index))
        self.nav_btns[page_index] = btn
        return btn

    def _start_tour_from_help(self, guide_id):
        return bool(self.tour_engine.start(guide_id))

    def _check_tour_precondition(self, precondition):
        if precondition == "PROJECT_OPEN":
            return self.project_service.current_project is not None
        if precondition == "MEDIA_LOADED":
            return bool(self.queue_mgr.active_vid)
        if precondition == "NO_BACKGROUND_JOB":
            return not bool(getattr(self, "_queue_generation_active", False))
        return False

    def create_side_action_button(self, text, slot):
        btn = QPushButton(text)
        btn.setFixedHeight(30)
        btn.setStyleSheet(f"QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 6px; color: {Theme.TEXT_PRIMARY}; text-align: left; padding-left: 10px; font-weight: 600; font-size: 11px; }} QPushButton:hover {{ border: 1px solid {Theme.CYAN}; color: {Theme.CYAN}; background-color: {Theme.SURFACE_SOFT}; }}")
        btn.clicked.connect(slot)
        return btn

    def switch_page(self, original_index):
        self._active_nav_index = original_index
        is_editor_workspace = original_index in (1, 2)
        
        # Hướng trang 1 & 2 vào chung Workspace (Index 1)
        target_stack_idx = 1 if is_editor_workspace else (original_index - 1 if original_index > 2 else original_index)
        self.stack.setCurrentIndex(target_stack_idx)

        # Quản lý Ẩn/Hiện Global Output Bar
        if hasattr(self, 'bottom_frame'):
            self.bottom_frame.setVisible(not is_editor_workspace)

        # Xử lý riêng cho Draft Center (chỉ chạy 1 lần)
        if original_index == 4:
            default_dir = self.out_input.text().strip() or (os.path.dirname(next(iter(self.queue_mgr.get_items()))) if self.queue_mgr.get_items() else "")
            self.page_drafts.set_directory(default_dir)

        # Cập nhật UI Sidebar
        target_btn = self.nav_btns.get(original_index)
        if target_btn:
            target_y = target_btn.y() + (target_btn.height() - self.sidebar_indicator.height()) // 2
            target_pos = QPoint(4, target_y)
            
            if not self.sidebar_indicator.isVisible() or self.sidebar_indicator.pos() == QPoint(0,0):
                self.sidebar_indicator.move(target_pos)
                self.sidebar_indicator.show()
            else:
                self.indicator_anim.stop()
                self.indicator_anim.setStartValue(self.sidebar_indicator.pos())
                self.indicator_anim.setEndValue(target_pos)
                self.indicator_anim.start()

        for idx, btn in self.nav_btns.items():
            if idx == original_index:
                btn.setStyleSheet(f"QPushButton {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.CYAN}; text-align: left; padding-left: 12px; border-radius: 6px; font-weight: bold; font-size: 12px; border: none; }}")
                clean_title = re.sub(r"[^\w\s]", "", btn.text()).strip()
                self.lbl_page_title.setText(clean_title)
            else:
                btn.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {Theme.TEXT_SECONDARY}; text-align: left; padding-left: 12px; border-radius: 6px; font-weight: 600; font-size: 12px; border: none; }} QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
            self.setStyleSheet(f"QMainWindow {{ background-color: {Theme.BG_APP}; border: 2px solid {Theme.PRIMARY_PURPLE}; }}")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(Theme.get_global_stylesheet())
        event.accept()

    def dropEvent(self, event):
        self.setStyleSheet(Theme.get_global_stylesheet())
        urls = event.mimeData().urls()
        valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')
        added = []
        for u in urls:
            f = u.toLocalFile()
            if f.lower().endswith(valid_exts) and self.queue_mgr.add_video(f):
                added.append(f)
        if added:
            self._start_metadata_worker(added)
            self.on_queue_item_clicked(added[-1], fresh_project=True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Only the 42px topbar is a drag handle. Child widgets such as
            # dock controls must keep their native mouse interaction.
            self._is_dragging = event.pos().y() <= 42
            if self._is_dragging:
                self.old_pos = event.globalPosition().toPoint()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._is_dragging:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def apply_saved_settings(self):
        s = load_settings()
        if not s: return
        if "motion_preset" in s:
            idx = self.page_settings.motion_preset_combo.findData(s["motion_preset"])
            if idx >= 0: self.page_settings.motion_preset_combo.setCurrentIndex(idx)
        if "sub_appear" in s:
            idx = self.page_settings.appear_combo.findData(s["sub_appear"])
            if idx >= 0: self.page_settings.appear_combo.setCurrentIndex(idx)
        if "sub_disappear" in s:
            idx = self.page_settings.disappear_combo.findData(s["sub_disappear"])
            if idx >= 0: self.page_settings.disappear_combo.setCurrentIndex(idx)
        if "text_effect" in s:
            idx = self.page_settings.text_effect_combo.findData(s["text_effect"])
            if idx >= 0: self.page_settings.text_effect_combo.setCurrentIndex(idx)

        self.apply_motion_config_to_player()
        
        if "output_dir" in s:
            self.out_input.setText(s["output_dir"])
            self.page_export.out_edit.setText(s["output_dir"])
        if "model_size" in s:
            idx = self.page_settings.model_combo.findData(s["model_size"])
            if idx >= 0: self.page_settings.model_combo.setCurrentIndex(idx)
        if "compute_type" in s:
            idx = self.page_settings.compute_combo.findData(s["compute_type"])
            if idx >= 0: self.page_settings.compute_combo.setCurrentIndex(idx)
        if "use_vad" in s:
            self.page_settings.chk_vad.setChecked(s["use_vad"])
        if "min_silence_ms" in s:
            self.page_settings.silence_spin.setValue(s.get("min_silence_ms", 500))
        if "do_hardsub" in s:
            self.page_settings.chk_hardsub_enable.setChecked(s["do_hardsub"])
        if "font_name" in s:
            self.page_settings.font_combo.setCurrentText(s["font_name"])
        if "font_size" in s:
            self.page_settings.size_spin.setValue(s["font_size"])
    def on_motion_preset_changed(self):
        preset = self.page_settings.motion_preset_combo.currentData()
        
        self.page_settings.appear_combo.blockSignals(True)
        self.page_settings.disappear_combo.blockSignals(True)
        self.page_settings.text_effect_combo.blockSignals(True)

        preset_values = {
            "minimal": ("fade", "fade", "normal"),
            "standard": ("fade", "fade", "normal"),
            "dynamic": ("rise", "drop", "highlight"),
            "off": ("instant", "instant", "normal"),
        }.get(preset)
        if preset_values:
            for combo, value in zip(
                (self.page_settings.appear_combo, self.page_settings.disappear_combo, self.page_settings.text_effect_combo),
                preset_values,
            ):
                combo.setCurrentIndex(combo.findData(value))

        self.page_settings.appear_combo.blockSignals(False)
        self.page_settings.disappear_combo.blockSignals(False)
        self.page_settings.text_effect_combo.blockSignals(False)

        self.apply_motion_config_to_player()

    def apply_motion_config_to_player(self):
        if not hasattr(self.video_player, 'anim_config') or not hasattr(self.video_player, 'anim_controller'):
            return

        preset = self.page_settings.motion_preset_combo.currentData()
        appear = self.page_settings.appear_combo.currentData()
        disappear = self.page_settings.disappear_combo.currentData()
        effect = self.page_settings.text_effect_combo.currentData()

        if preset == "off":
            self.video_player.anim_config.enabled = False
        else:
            self.video_player.anim_config.enabled = True
            self.video_player.anim_config.fade_in_ms = 120 if preset == "minimal" else (200 if preset == "dynamic" else 160)
            self.video_player.anim_config.fade_out_ms = 120 if preset == "minimal" else (200 if preset == "dynamic" else 160)

        appear_map = {
            "fade": SubtitleAppearMode.FADE,
            "rise": SubtitleAppearMode.RISE,
            "instant": SubtitleAppearMode.INSTANT,
            "reveal": SubtitleAppearMode.REVEAL
        }
        self.video_player.anim_config.appear_mode = appear_map.get(appear, SubtitleAppearMode.FADE)

        disappear_map = {
            "fade": SubtitleDisappearMode.FADE,
            "drop": SubtitleDisappearMode.DROP,
            "instant": SubtitleDisappearMode.INSTANT
        }
        self.video_player.anim_config.disappear_mode = disappear_map.get(disappear, SubtitleDisappearMode.FADE)

        effect_map = {
            "normal": SubtitleTextEffect.NORMAL,
            "reveal": SubtitleTextEffect.REVEAL,
            "highlight": SubtitleTextEffect.HIGHLIGHT
        }
        self.video_player.anim_config.text_effect = effect_map.get(effect, SubtitleTextEffect.NORMAL)

        self.video_player.anim_controller.update_config(self.video_player.anim_config)

    def update_hardware_info(self):
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                alloc = torch.cuda.memory_allocated(0) / (1024**3)
                vram_str = f"{alloc:.1f} / {total:.1f} GB"
            else:
                gpu_name, vram_str = "CPU Only", "N/A"
        except (ImportError, RuntimeError, AttributeError):
            gpu_name, vram_str = "RTX GPU", "--"

        self.page_dashboard.update_hardware(gpu_name, vram_str, self.page_dashboard.card_cpu_val.text(), self.page_dashboard.card_status_val.text())

    def update_cpu_usage(self):
        try:
            import psutil
            cpu_str = f"{psutil.cpu_percent(interval=None):.1f}%"
            self.page_dashboard.card_cpu_val.setText(cpu_str)
        except (ImportError, OSError, RuntimeError):
            return

    def _start_metadata_worker(self, video_paths):
        if not video_paths: return
        if not hasattr(self, 'meta_workers'): self.meta_workers = []
        w = MetadataWorker(video_paths)
        w.metadata_parsed.connect(self.queue_mgr.update_metadata)
        w.finished.connect(lambda worker=w: self.meta_workers.remove(worker) if worker in self.meta_workers else None)
        self.meta_workers.append(w)
        w.start()

    def select_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if files:
            added = [f for f in files if self.queue_mgr.add_video(f)]
            self._start_metadata_worker(added)
            if added:
                self.on_queue_item_clicked(added[-1], fresh_project=True)

    def select_srt_for_video(self):
        vid, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if vid:
            srt, _ = QFileDialog.getOpenFileName(self, "Chọn file Phụ đề / Draft", "", "Subtitle & Draft (*.srt *.ai-subtitle-draft)")
            if srt:
                if vid not in self.queue_mgr.get_items():
                    self.queue_mgr.add_video(vid)
                    self._start_metadata_worker([vid])
                self.queue_mgr.set_srt_for_video(vid, srt)
                self.on_queue_item_clicked(vid)

    def clear_files(self):
        self._queue_project_dirs.clear()
        self.queue_mgr.clear_queue()

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu kết quả")
        if d:
            self.out_input.setText(d)
            self.page_export.out_edit.setText(d)

    def on_queue_updated(self):
        items = self.queue_mgr.get_items()
        self.queue_ui.sync_with_manager(items, self.queue_mgr.active_vid)
        count = len(items)
        self.page_dashboard.lbl_queue_overview.setText(f"Queue: {count} videos loaded | Output: {self.out_input.text() or 'Default'}")
        
        if count == 0:
            self.video_player.cleanup()
            self.timeline_widget.clear()  
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            self.video_player.sub_controller.load_srt(None)

    def on_queue_item_clicked(self, vid_path, fresh_project=False):
        self.queue_mgr.set_active(vid_path)

        # Queue items can arrive through Drag & Drop without going through
        # the New Project dialog. SubtitleGenerationService requires a
        # project because its checkpoint and canonical artifact live there.
        if fresh_project:
            self._queue_project_dirs.pop(vid_path, None)

        if self.project_service.requires_project_switch(
            vid_path, fresh_project=fresh_project
        ):
            file_name = os.path.basename(vid_path)
            output_dir = self.out_input.text().strip() or os.path.dirname(vid_path)
            project_dir = self._queue_project_dirs.get(vid_path)

            try:
                if fresh_project:
                    self.project_service.create_auto_project(
                        output_dir,
                        file_name,
                        vid_path,
                        uuid.uuid4().hex[:8],
                    )
                    project_dir = self.project_service.project_dir
                elif project_dir and os.path.exists(project_dir):
                    self.project_service.open_project(project_dir)
                else:
                    safe_name = "".join(
                        char if char.isalnum() else "_" for char in file_name
                    )
                    project_dir = os.path.join(
                        output_dir, f"{safe_name}.ai-subtitle"
                    )
                    if not os.path.exists(project_dir):
                        self.project_service.create_project(
                            project_dir, file_name, vid_path
                        )
                    else:
                        self.project_service.open_project(project_dir)
                self._queue_project_dirs[vid_path] = project_dir
                self.generation_panel.check_resumable_state()
                self._refresh_transcription_context_views()
                self.append_log(
                    f"📦 [HỆ THỐNG] Đã tự động tạo/nạp dự án cho video: {file_name}"
                )
            except (OSError, RuntimeError, ValueError) as exc:
                # Never leave another video's project active after a failed
                # auto-project switch.
                self.project_service.close_project()
                self.append_log(
                    f"❌ [LỖI] Không thể tự động tạo/nạp dự án: {exc}"
                )

        _, srt_path = self.queue_mgr.get_active_data()
        self.video_player.load_video(vid_path)

        # 1. [FIX REVIEW 1] LUÔN LOAD SRT VÀO GIAO DIỆN TRƯỚC ĐỂ TRÁNH LỖI TRỐNG DỮ LIỆU
        if srt_path and os.path.exists(srt_path):
            if srt_path.endswith('.ai-subtitle-draft'):
                self.sub_editor.load_draft_file(srt_path)
            else:
                self.sub_editor.load_srt_file(srt_path)
            self.video_player.sub_controller.load_srt(srt_path)
        else:
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            self.video_player.sub_controller.load_srt(None)

        # 2. KHỞI CHẠY LUỒNG SÓNG ÂM (Background Worker)
        from core.waveform.waveform_service import WaveformService
        def _load_waveform():
            # [FIX REVIEW 1] Luồng này giờ chỉ thuần túy xử lý audio, tuyệt đối không chạm vào UI State
            print(f"[DEBUG-WAVEFORM] Bắt đầu nạp sóng âm cho: {vid_path}")
            try:
                video_data = self.queue_mgr.get_items().get(vid_path, {})
                duration_sec = video_data.get('duration', 0)
                duration_ms = int(duration_sec * 1000)

                peaks = None
                try:
                    peaks = WaveformService.generate_waveform_peaks(vid_path)
                except (OSError, RuntimeError, ValueError) as e:
                    print(f"[DEBUG-WAVEFORM] ❌ LỖI Trích xuất sóng âm: {e}")

                if duration_ms <= 0 and peaks is not None and len(peaks) > 0:
                    duration_ms = int((len(peaks) / 100.0) * 1000)
                
                if duration_ms <= 0:
                    duration_ms = 3600000 

                # Báo cáo kết quả về Main Thread
                self.waveform_ready_signal.emit(vid_path, duration_ms, peaks)
                
            except (OSError, RuntimeError, ValueError) as e:
                print(f"[DEBUG-WAVEFORM] ❌ LỖI TỔNG QUÁT LUỒNG SÓNG ÂM: {e}")

        threading.Thread(target=_load_waveform, daemon=True).start()
        # ---------------------------------------------------

        if srt_path and os.path.exists(srt_path):
            if srt_path.endswith('.ai-subtitle-draft'):
                self.sub_editor.load_draft_file(srt_path)
            else:
                self.sub_editor.load_srt_file(srt_path)
            self.video_player.sub_controller.load_srt(srt_path)
        else:
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            self.video_player.sub_controller.load_srt(None)

    def on_queue_item_removed_handler(self, vid_path):
        self._queue_project_dirs.pop(vid_path, None)
        items = self.queue_mgr.get_items()
        if not items:
            self.video_player.cleanup()
            self.timeline_widget.clear()  
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            self.video_player.sub_controller.load_srt(None)
        elif self.queue_mgr.active_vid:
            self.on_queue_item_clicked(self.queue_mgr.active_vid)

    def _load_draft_from_center(self, draft_path, silent=False):
        if not draft_path or not os.path.exists(draft_path):
            Toast.show_error(self, "Tập tin Draft không tồn tại.")
            return False

        draft_filename = os.path.basename(draft_path)
        base_key = draft_filename.replace(".ai-subtitle-draft", "").replace("_timing", "")
        
        target_vid = None
        for vid in self.queue_mgr.get_items():
            vid_name = os.path.splitext(os.path.basename(vid))[0]
            if vid_name == base_key or vid_name.startswith(base_key) or base_key.startswith(vid_name):
                target_vid = vid
                break

        if not target_vid:
            Toast.show_error(self, "Vui lòng nạp video gốc tương ứng vào Queue trước khi mở Draft.")
            return False

        self.queue_mgr.set_active(target_vid)
        self.queue_mgr.set_srt_for_video(target_vid, draft_path)

        self.video_player.load_video(target_vid)
        self.sub_editor.load_draft_file(draft_path)
        self.video_player.sub_controller.load_srt(draft_path)

        self.switch_page(1)
        self.bottom_tabs.setCurrentIndex(0)
        
        if not silent:
            Toast.show_info(self, f"Đã nạp bản nháp: {draft_filename}")
        return True

    def _trigger_export_hardsub(self):
        if not self.queue_mgr.active_vid:
            Toast.show_error(self, "Vui lòng chọn video từ Workspace để hardsub.")
            return
            
        _, srt_path = self.queue_mgr.get_active_data()
        if not srt_path or not os.path.exists(srt_path):
            Toast.show_error(self, "Không tìm thấy file phụ đề SRT tương ứng.")
            return
            
        if srt_path.lower().endswith('.ai-subtitle-draft'):
            Toast.show_error(self, "Draft chưa phải SRT. Hãy mở Draft và chọn Lưu SRT (Softsub) trước khi Hardsub.")
            return
            
        if hasattr(self, 'worker') and self.worker.isRunning():
            Toast.show_info(self, "Hệ thống đang bận xử lý, vui lòng chờ...")
            return
            
        out_dir = self.page_export.out_edit.text().strip() or self.out_input.text().strip()
        
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.page_dashboard.quick_progress.setValue(0)
        self.page_dashboard.card_status_val.setText("Processing")
        
        self.worker = HardsubWorker(
            video_path=self.queue_mgr.active_vid,
            srt_path=srt_path,
            output_dir=out_dir,
            font_size=self.page_settings.size_spin.value(),
            font_color="white",
            font_name=self.page_settings.font_combo.currentText()
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        
        self.worker.finished_signal.connect(self._on_manual_hardsub_success)
        self.worker.error_signal.connect(self._on_manual_hardsub_error)
        self.worker.start()

    def _on_manual_hardsub_success(self, msg, path):
        from core.artifacts.artifact_types import ArtifactType
        self._register_artifact(path, ArtifactType.HARDSUB, {"mode": "manual_hardsub"})
        if getattr(self, 'project_service', None) and self.project_service.current_project:
            self.project_service.current_project.state.export_status = "READY"

        Toast.show_success(self, f"Render Hardsub xong: {path}")
        self.progress_bar.setValue(100)
        self.page_dashboard.quick_progress.setValue(100)
        QTimer.singleShot(2500, self._cleanup_ui_after_task)

    def _on_manual_hardsub_error(self, err):
        Toast.show_error(self, f"Lỗi Hardsub: {err}")
        self._cleanup_ui_after_task()

    def _restore_panel_callbacks(self):
        """Return subtitle-generation callbacks to the interactive drawer."""
        if not hasattr(self, "generation_panel"):
            return
        self.subtitle_generation_service.on_progress = (
            self.generation_panel._update_progress
        )
        self.subtitle_generation_service.on_error = self.generation_panel._on_error
        self.subtitle_generation_service.on_finish = (
            self._on_interactive_generation_finished
        )
        self.subtitle_generation_service.on_batch_complete = (
            self._on_generation_batch_sync
        )

    def _queue_update_progress(self, percent, message):
        """Mirror Queue generation progress in the global bar and drawer."""
        self.update_progress(percent, message)
        if hasattr(self, "generation_panel"):
            self.generation_panel._update_progress(percent, message)

    @staticmethod
    def _parse_queue_duration_ms(value) -> int:
        """Parse Queue metadata duration, which is normally HH:MM:SS."""
        if isinstance(value, (int, float)):
            return max(0, int(float(value) * 1000))
        if not isinstance(value, str):
            return 0
        parts = value.strip().split(":")
        if len(parts) != 3:
            return 0
        try:
            hours, minutes, seconds = (int(part) for part in parts)
            return max(0, (hours * 3600 + minutes * 60 + seconds) * 1000)
        except ValueError:
            return 0

    def _queue_video_duration_ms(self, video_path: str) -> int:
        queue_data = self.queue_mgr.get_items().get(video_path, {})
        metadata = queue_data.get("metadata") or {}
        duration_ms = self._parse_queue_duration_ms(
            metadata.get("duration", queue_data.get("duration", 0))
        )
        if duration_ms > 0:
            return duration_ms

        # Metadata is asynchronous; obtain a reliable fallback before the
        # planner creates time batches.
        try:
            from workers.TaskQueue import get_video_duration

            duration_sec = get_video_duration(video_path)
            if duration_sec > 0:
                return int(duration_sec * 1000)
        except (OSError, RuntimeError, ValueError) as exc:
            self.append_log(f"[QUEUE] Không đọc được thời lượng video: {exc}")
        return 3600000

    def start_processing(self):
        items = self.queue_mgr.get_items()
        if not items: return
        self.is_cancelled_flag = False
        self._queue_generation_active = False
        self.batch_queue = [(vid, data.get("srt_path")) for vid, data in items.items()]
        self.total_batch_items = len(self.batch_queue)
        self.current_batch_index = 0
        self.output_dir = (
            self.out_input.text().strip()
            or self.page_export.out_edit.text().strip()
            or os.path.dirname(next(iter(items)))
        )

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.page_dashboard.card_status_val.setText("Processing")
        self.log_box.clear()
        self.process_next_batch_item()

    def process_next_batch_item(self):
        if (
            getattr(self, "is_cancelled_flag", False)
            or not hasattr(self, "batch_queue")
            or not self.batch_queue
        ):
            if not getattr(self, "is_cancelled_flag", False):
                self.process_finished("Toàn bộ tiến trình Queue đã hoàn tất!")
            return

        self.current_batch_index += 1
        self.current_vid, current_srt = self.batch_queue.pop(0)
        file_name = os.path.basename(self.current_vid)
        self.append_log("\n==================================================")
        self.append_log(
            f"🎬 ĐANG XỬ LÝ [{self.current_batch_index}/{self.total_batch_items}]: "
            f"{file_name}"
        )
        self.append_log("==================================================")
        self.on_queue_item_clicked(self.current_vid)

        if not current_srt:
            if not self.project_service.is_current_project_for_video(
                self.current_vid
            ):
                self.process_error(
                    "Project tự động không khớp với video đang xử lý."
                )
                return

            duration_ms = self._queue_video_duration_ms(self.current_vid)
            self.generation_panel.set_video_duration(duration_ms)
            self.append_log(
                "[ASR] Đang nạp Audio và phân bổ Time-Batching "
                "(chống tràn VRAM)..."
            )

            self.subtitle_generation_service.on_progress = (
                self._queue_update_progress
            )
            self.subtitle_generation_service.on_error = self.process_error
            self.subtitle_generation_service.on_finish = (
                self.on_queue_generation_finished
            )
            self.subtitle_generation_service.on_batch_complete = (
                self._on_generation_batch_sync
            )
            self._queue_generation_active = True

            project = self.project_service.current_project
            settings = self.page_settings
            compiled_context = self.subtitle_generation_service.compile_prompt_context(
                project.transcription_context
            )
            request = SubtitleGenerationRequest(
                request_id=str(uuid.uuid4()),
                project_id=project.project_id,
                source_fingerprint=project.source.fingerprint,
                video_path=self.current_vid,
                model_size=settings.model_combo.currentData(),
                compute_type=settings.compute_combo.currentData(),
                language=None,
                use_vad=settings.chk_vad.isChecked(),
                min_silence_ms=settings.silence_spin.value(),
                word_timestamps=False,
                batch_mode="time",
                batch_size_value=5,
                overlap_ms=2000,
                prompt_context=compiled_context.text,
            )
            try:
                self.subtitle_generation_service.start_generation(
                    request, duration_ms
                )
            except (OSError, RuntimeError, ValueError) as exc:
                self.process_error(f"Lỗi khởi chạy Subtitle Generation: {exc}")
            return

        if current_srt.endswith(".ai-subtitle-draft"):
            self.append_log(
                "❌ File Draft cần được lưu thành SRT trước khi Hardsub."
            )
            self.process_next_batch_item()
            return

        if not self.page_settings.chk_hardsub_enable.isChecked():
            self.append_log(
                "[HỆ THỐNG] Hardsub tự động đang tắt. "
                "Bỏ qua Hardsub cho video hiện tại."
            )
            self.process_next_batch_item()
            return

        self.worker = HardsubWorker(
            video_path=self.current_vid,
            srt_path=current_srt,
            output_dir=self.output_dir,
            font_size=self.page_settings.size_spin.value(),
            font_color="white",
            font_name=self.page_settings.font_combo.currentText(),
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_hardsub_finished)
        self.worker.error_signal.connect(self.process_error)
        self.worker.start()

    def on_queue_generation_finished(self):
        """Continue Queue processing using the canonical artifact's shadow SRT."""
        self._queue_generation_active = False
        self._restore_panel_callbacks()
        project = self.project_service.current_project
        artifact_id = (
            getattr(project.state, "subtitle_artifact_id", None)
            if project
            else None
        )
        artifact = self.artifact_store.get(artifact_id) if artifact_id else None
        if not artifact or not artifact.path:
            self.process_error("Không tìm thấy Subtitle Artifact sau khi tạo.")
            return

        shadow_srt = artifact.path.replace(".sub.json", "_shadow.srt")
        if not os.path.exists(shadow_srt):
            self.process_error("Không tìm thấy Shadow SRT sau khi tạo phụ đề.")
            return

        self.append_log(f"[AI] Đã hoàn tất tạo phụ đề. File: {shadow_srt}")
        self.queue_mgr.set_srt_for_video(self.current_vid, shadow_srt)

        if not self.page_settings.chk_hardsub_enable.isChecked():
            self.append_log(
                "[HỆ THỐNG] Hardsub tự động đang tắt. "
                "Chuyển sang video tiếp theo..."
            )
            self.process_next_batch_item()
            return

        out_dir = self.page_export.out_edit.text().strip() or self.output_dir
        self.worker = HardsubWorker(
            video_path=self.current_vid,
            srt_path=shadow_srt,
            output_dir=out_dir,
            font_size=self.page_settings.size_spin.value(),
            font_color="white",
            font_name=self.page_settings.font_combo.currentText(),
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_hardsub_finished)
        self.worker.error_signal.connect(self.process_error)
        self.worker.start()

    # ==========================================================
    # [SPRINT 9] REAL-TIME SUBTITLE GENERATION SYNC
    # ==========================================================
    def _start_timing_draft(self, batch_minutes: int, settings: dict):
        """Start the legacy VAD-only draft pipeline from the new panel."""
        try:
            self.timing_service.start_timing(batch_minutes, settings)
        except (OSError, RuntimeError, ValueError) as exc:
            self._on_timing_error(str(exc))

    def _resume_timing_draft(self, batch_minutes: int, settings: dict):
        """Continue the Timing checkpoint without entering the ASR pipeline."""
        try:
            checkpoint = self.project_service.load_timing_checkpoint()
            if checkpoint and checkpoint.timing_artifact_id:
                self.timing_service.continue_timing(batch_minutes, settings)
            else:
                # No Timing Artifact exists when cancellation happens before
                # the first batch commits, so there is nothing to continue.
                self.timing_service.start_timing(batch_minutes, settings)
        except (OSError, RuntimeError, ValueError) as exc:
            self._on_timing_error(str(exc))

    def _on_timing_progress(self, percent: int, message: str):
        percent = max(0, min(100, int(percent)))
        self.generation_panel._update_progress(percent, message)
        self.progress_bar.setValue(percent)
        self.page_dashboard.quick_progress.setValue(percent)
        if message:
            self.lbl_speed_eta.setText(message)

    def _on_timing_log(self, message: str):
        self.append_log(f"[TIMING] {message}")

    def _on_timing_error(self, message: str):
        self.append_log(f"❌ [TIMING] {message}")
        self.generation_panel._on_error(message)
        self.page_dashboard.card_status_val.setText("FAILED")

    def _on_timing_state_changed(self, status: str, message: str):
        self.generation_panel.lbl_status.setText(message)
        self.page_dashboard.card_status_val.setText(status)

        if status in {"READY", "IDLE", "COMPLETED", "FAILED"}:
            self.generation_panel._reset_ui_state()
            if status != "FAILED":
                self.generation_panel.progress_bar.setValue(
                    100 if status == "COMPLETED" else 0
                )
        else:
            self.generation_panel._set_ui_state_running()

    def _on_timing_batch_completed(self, _added_count: int, _batch_size: int):
        """Load the committed timing SRT immediately after a successful batch."""
        project = self.project_service.current_project
        if not project:
            return
        artifact_id = getattr(project.state.timing, "timing_artifact_id", None)
        artifact = self.artifact_store.get(artifact_id) if artifact_id else None
        if not artifact or not artifact.path or not os.path.exists(artifact.path):
            return

        source_path = getattr(getattr(project, "source", None), "path", "")
        if source_path:
            self.queue_mgr.set_srt_for_video(source_path, artifact.path)

        active_video = self.queue_mgr.active_vid
        if not active_video or not self.project_service.is_current_project_for_video(
            active_video
        ):
            self.append_log(
                "[TIMING] Đã lưu Draft cho video nền; UI hiện đang chọn video khác."
            )
            self.generation_panel.refresh_batch_mode_availability()
            return

        try:
            self.sub_editor.load_srt_file(artifact.path)
            self.video_player.sub_controller.load_srt(artifact.path)
            duration_ms = self.generation_panel.video_duration_ms
            if duration_ms <= 0 and hasattr(self.video_player, "player"):
                duration_ms = self.video_player.player.duration()
            if duration_ms <= 0:
                duration_ms = 3600000
            self.timeline_data_provider.load_runtime_data(
                self.sub_editor.all_segments, duration_ms
            )
            self.timeline_widget.load_project_data(
                duration_ms, self.timeline_data_provider.get_all_segments()
            )
            self.generation_panel.refresh_batch_mode_availability()
        except (OSError, RuntimeError, ValueError) as exc:
            self.append_log(f"[TIMING] Không đồng bộ được Draft lên UI: {exc}")

    def _on_generation_batch_sync(self, batch=None, segments=None):
        """Persist the generated Shadow SRT without disturbing the active editor."""
        for segment in segments or []:
            start_str = self.timing_service._ms_to_time_str(segment.start_ms)
            end_str = self.timing_service._ms_to_time_str(segment.end_ms)
            self.append_log(f"[{start_str} --> {end_str}] {segment.text}")

        project = self.project_service.current_project
        if not project or not project.state.subtitle_artifact_id:
            return None

        artifact = self.project_service.artifact_store.get(
            project.state.subtitle_artifact_id
        )
        if not artifact or not os.path.exists(artifact.path):
            return None

        try:
            import json

            with open(artifact.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            subtitles = [
                (segment["start_ms"], segment["end_ms"], segment["text"])
                for segment in data.get("segments", [])
            ]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.append_log(f"[SYNC] Không đọc được Subtitle Artifact: {exc}")
            return None

        shadow_srt_path = artifact.path.replace(".sub.json", "_shadow.srt")
        temp_srt_path = f"{shadow_srt_path}.tmp"
        try:
            from core.subtitle_exporter import SubtitleExportService

            SubtitleExportService.export_srt(subtitles, temp_srt_path)
            os.replace(temp_srt_path, shadow_srt_path)
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            if os.path.exists(temp_srt_path):
                os.remove(temp_srt_path)
            self.append_log(f"[SYNC] Không tạo được Shadow SRT: {exc}")
            return None

        return shadow_srt_path

    def _on_interactive_generation_finished(self):
        """Publish the completed ASR result once, preserving editor pagination."""
        shadow_srt_path = self._on_generation_batch_sync()
        if shadow_srt_path:
            self._load_generated_subtitles_into_ui(shadow_srt_path)
        self.generation_panel._on_finish()

    def _load_generated_subtitles_into_ui(self, shadow_srt_path):
        """Reload editor, player and timeline only after a full ASR run completes."""

        self.sub_editor.load_srt_file(shadow_srt_path)
        self.video_player.sub_controller.load_srt(shadow_srt_path)

        duration_ms = self.generation_panel.video_duration_ms
        if duration_ms <= 0 and hasattr(self.video_player, "player"):
            duration_ms = self.video_player.player.duration()
        if duration_ms <= 0:
            duration_ms = 3600000

        self.timeline_data_provider.load_runtime_data(
            self.sub_editor.all_segments, duration_ms
        )
        self.timeline_widget.load_project_data(
            duration_ms, self.timeline_data_provider.get_all_segments()
        )

        last_index = self.sub_editor.table.rowCount() - 1
        if last_index >= 0:
            item = self.sub_editor.table.item(last_index, 0)
            if item:
                self.sub_editor.table.scrollToItem(item)

    def on_hardsub_finished(self, msg, out_video_path):
        from core.artifacts.artifact_types import ArtifactType
        self._register_artifact(out_video_path, ArtifactType.HARDSUB, {"mode": "auto_queue_hardsub"})
        if getattr(self, 'project_service', None) and self.project_service.current_project:
            self.project_service.current_project.state.export_status = "READY"

        self.append_log(f"[FFmpeg] Xuất file thành công: {out_video_path}")
        self.process_next_batch_item()

    def cancel_processing(self):
        self.is_cancelled_flag = True
        self.batch_queue = []
        if getattr(self, "_queue_generation_active", False):
            self._queue_generation_active = False
            # Prevent cancel_generation() from dispatching the Queue finish
            # callback while the user is explicitly aborting the Queue.
            self.subtitle_generation_service.on_finish = None
            self.subtitle_generation_service.cancel_generation()
            self._restore_panel_callbacks()
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("[HỆ THỐNG] Đang dừng an toàn...")
            self.cancel_btn.setEnabled(False)
        self._cleanup_ui_after_task()

    def update_progress(self, val, msg):
        global_val = val
        if hasattr(self, 'total_batch_items') and self.total_batch_items > 0:
            base_p = ((self.current_batch_index - 1) / self.total_batch_items) * 100
            global_val = int(base_p + (val / self.total_batch_items))
        self.progress_anim.stop()
        self.progress_anim.setStartValue(self.progress_bar.value())
        self.progress_anim.setEndValue(global_val)
        self.progress_anim.start()
        self.page_dashboard.quick_progress.setValue(global_val)
        if msg:
            self.lbl_speed_eta.setText(msg)

    def append_log(self, msg):
        self.log_box.append(msg)
        self.page_dashboard.activity_log.append(msg)
        speed_match = re.search(r"speed=\s*([0-9\.]+x)", msg)
        if speed_match:
            self.lbl_speed_eta.setText(f"Speed: {speed_match.group(1)}")

    def process_finished(self, msg):
        self._queue_generation_active = False
        self._restore_panel_callbacks()
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.page_dashboard.card_status_val.setText("Idle")
        self.progress_anim.stop()
        self.progress_bar.setValue(0)
        
        self.page_dashboard.quick_progress.setValue(0) 
        
        self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
        Toast.show_success(self, msg)

        self._cleanup_ui_after_task()

    def process_error(self, err):
        queue_generation_active = getattr(self, "_queue_generation_active", False)
        self._queue_generation_active = False
        self._restore_panel_callbacks()

        if queue_generation_active:
            # The service already reported the failure. Cancel only to make
            # sure its worker exits, without invoking the Queue finish hook.
            self.subtitle_generation_service.on_finish = None
            self.subtitle_generation_service.cancel_generation()
            self._restore_panel_callbacks()

        self.append_log(f"❌ [LỖI] {err}")
        if getattr(self, "is_cancelled_flag", False):
            self._cleanup_ui_after_task()
            return

        if hasattr(self, "batch_queue") and self.batch_queue:
            self.append_log("[HỆ THỐNG] Bỏ qua video lỗi, tiếp tục video tiếp theo trong Queue...")
            self.process_next_batch_item()
            return

        self._cleanup_ui_after_task()

    def _cleanup_ui_after_task(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        if hasattr(self, 'progress_anim'):
            self.progress_anim.stop()
            
        self.progress_bar.setValue(0)
        self.page_dashboard.quick_progress.setValue(0)
        self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
        self.page_dashboard.card_status_val.setText("Idle")

    def open_output_folder(self):
        out_d = self.out_input.text().strip() or (os.path.dirname(next(iter(self.queue_mgr.get_items()))) if self.queue_mgr.get_items() else "")
        if out_d and os.path.exists(out_d):
            os.startfile(out_d)

    def on_transcription_context_committed(
        self, new_context: TranscriptionContext
    ) -> None:
        project = self.project_service.current_project
        if project is None:
            return
        normalized = new_context.normalized()
        current = getattr(project, "transcription_context", TranscriptionContext())
        if current.normalized() == normalized:
            return
        project.transcription_context = normalized
        self.project_service.mark_dirty()
        self._refresh_transcription_context_views(sync_editor=False)

    def _refresh_transcription_context_views(self, *, sync_editor: bool = True) -> None:
        project = getattr(self.project_service, "current_project", None)
        if project is None or not hasattr(self, "context_panel"):
            return
        context = getattr(project, "transcription_context", TranscriptionContext())
        compiled = self.subtitle_generation_service.compile_prompt_context(context)
        if sync_editor:
            self.context_panel.set_context(context)
        self.context_panel.set_prompt_diagnostics(compiled)
        self.generation_panel.set_context_status(
            compiled, configured=bool(context.context.strip() or context.glossary)
        )

    def _show_context_inspector(self) -> None:
        self.generation_dock.show()
        self.dock_tabs.setCurrentWidget(self.context_panel)

    def capture_recovery_working_state(self) -> RecoveryWorkingState:
        workspace = self.workspace_service.capture_workspace() or {}
        project = self.project_service.current_project
        source = getattr(project, "source", None)
        session = getattr(self.recovery_manager, "_active_session", None)
        context = getattr(project, "transcription_context", None)
        context_data = (
            asdict(context.normalized())
            if isinstance(context, TranscriptionContext)
            else {}
        )
        return RecoveryWorkingState(
            schema_version=2.0,
            session_id=session.session_id if session else "",
            project_id=getattr(project, "project_id", None),
            project_file_path=self.project_service.project_dir or "",
            video_path=getattr(source, "path", "") if source else "",
            source_fingerprint=getattr(source, "fingerprint", "") if source else "",
            edit_revision=self.revision_tracker.edit_revision,
            segments=copy.deepcopy(getattr(self.sub_editor, "all_segments", [])),
            workspace_state=copy.deepcopy(workspace),
            transcription_context=context_data,
        )

    def apply_recovery_working_state(self, state: RecoveryWorkingState, *, linked: bool) -> None:
        self.sub_editor.all_segments = copy.deepcopy(state.segments)
        if hasattr(self.sub_editor, "render_page"):
            self.sub_editor.render_page()
        if hasattr(self, "timeline_data_provider"):
            self.timeline_data_provider.load_runtime_data(state.segments, 0)
        if hasattr(self, "timeline_widget") and hasattr(self.timeline_widget, "load_project_data"):
            self.timeline_widget.load_project_data(0, state.segments, None)
        if state.workspace_state and getattr(self.project_service, "current_project", None):
            self.workspace_service.apply_workspace(state.workspace_state)
        context_data = getattr(state, "transcription_context", None)
        project = getattr(self.project_service, "current_project", None)
        if context_data and project:
            project.transcription_context = TranscriptionContext(
                context=context_data.get("context", ""),
                glossary=context_data.get("glossary", []),
            ).normalized()
        self.global_undo_manager.clear()
        manifest = getattr(getattr(self.recovery_manager, "_active_session", None), "manifest", None)
        self.revision_tracker.restore_from_snapshot(
            state.edit_revision,
            getattr(manifest, "last_saved_revision", 0),
            getattr(manifest, "last_clean_revision", 0),
        )
        self._update_window_title_dirty_marker(True)
        self._refresh_transcription_context_views()

    def _on_autosave_timeout(self):
        if self.revision_tracker.is_dirty and self.revision_tracker.edit_revision > self.revision_tracker.snapshot_revision:
            self.recovery_manager.write_snapshot(self.capture_recovery_working_state())

    def _update_window_title_dirty_marker(self, is_dirty: bool):
        title = self.windowTitle().replace(" *", "")
        self.setWindowTitle(title + (" *" if is_dirty else ""))

    def closeEvent(self, event):
        if getattr(self, "revision_tracker", None) and self.revision_tracker.is_dirty:
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, 
                    "Lưu thay đổi?", 
                    f"Dự án '{self.project_service.current_project.name}' có thay đổi chưa được lưu.\nBạn có muốn lưu lại trước khi thoát không?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save
                )
                
                if reply == QMessageBox.Save:
                    if self.action_save_project():
                        self.recovery_manager.finalize_clean_shutdown()
                    else:
                        event.ignore()
                        return
                elif reply == QMessageBox.Discard:
                    session = getattr(self.recovery_manager, "_active_session", None)
                    if session:
                        self.recovery_manager.discard_session(session.session_id)
                elif reply == QMessageBox.Cancel:
                    event.ignore()  
                    return
        elif getattr(self, "recovery_manager", None):
            self.recovery_manager.finalize_clean_shutdown()

        save_settings({
            "output_dir": self.out_input.text().strip(),
            "model_size": self.page_settings.model_combo.currentData(),
            "compute_type": self.page_settings.compute_combo.currentData(),
            "use_vad": self.page_settings.chk_vad.isChecked(),
            "min_silence_ms": self.page_settings.silence_spin.value(),
            "do_hardsub": self.page_settings.chk_hardsub_enable.isChecked(),
            "font_name": self.page_settings.font_combo.currentText(),
            "font_size": self.page_settings.size_spin.value()
        })
        
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
            
        try:
            import os
            import subprocess
            if os.name == 'nt':
                subprocess.Popen(["taskkill", "/f", "/im", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError:
            pass
            
        event.accept()
        
    def _trigger_export_softsub(self):
        if not self.queue_mgr.active_vid:
            Toast.show_error(self, "Vui lòng chọn video để xuất phụ đề.")
            return

        if not self.sub_editor.all_segments:
            Toast.show_error(self, "Không có dữ liệu phụ đề để xuất.")
            return

        out_dir = self.page_export.out_edit.text().strip() or self.out_input.text().strip()
        if not out_dir:
            Toast.show_error(self, "Vui lòng chọn thư mục lưu.")
            return
            
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            Toast.show_error(self, f"Lỗi hệ thống tập tin: {e!s}")
            return

        base_name = os.path.splitext(os.path.basename(self.queue_mgr.active_vid))[0]
        exported = []

        try:
            from core.artifacts.artifact_types import ArtifactType
            from core.subtitle_exporter import SubtitleExportService
            exporter = SubtitleExportService()
        except ImportError:
            Toast.show_error(self, "Lỗi nạp SubtitleExportService từ core. Kiểm tra lại module.")
            return

        subtitles_for_export = []
        for seg in self.sub_editor.all_segments:
            start_ms = self.sub_editor.time_str_to_ms(seg["start"])
            end_ms = self.sub_editor.time_str_to_ms(seg["end"])
            text = seg["text"] if seg["text"] != "[ Chưa có nội dung ]" else ""
            subtitles_for_export.append((start_ms, end_ms, text))

        try:
            if self.page_export.chk_srt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.srt")
                exporter.export_srt(subtitles_for_export, path)
                self._register_artifact(path, ArtifactType.EXPORT, {"format": "srt"})
                exported.append("SRT")
            
            if self.page_export.chk_vtt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.vtt")
                exporter.export_vtt(subtitles_for_export, path)
                self._register_artifact(path, ArtifactType.EXPORT, {"format": "vtt"})
                exported.append("VTT")

            if self.page_export.chk_txt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.txt")
                exporter.export_txt(subtitles_for_export, path)
                self._register_artifact(path, ArtifactType.EXPORT, {"format": "txt"})
                exported.append("TXT")

            if exported:
                if getattr(self, 'project_service', None) and self.project_service.current_project:
                    self.project_service.current_project.state.export_status = "READY"
                Toast.show_success(self, f"Đã xuất thành công: {', '.join(exported)}")
            else:
                Toast.show_info(self, "Vui lòng chọn ít nhất một định dạng xuất.")
        except (OSError, ValueError, RuntimeError) as e:
            Toast.show_error(self, f"Lỗi trong quá trình ghi file: {e!s}")

    def _continue_draft_from_center(self, draft_path):
        if not self._load_draft_from_center(draft_path, silent=True):
            return

        start_idx = None
        for i, seg in enumerate(self.sub_editor.all_segments):
            text = str(seg.get('text', '')).strip()
            if not text or text == "[ Chưa có nội dung ]":
                start_idx = i
                break
                
        if start_idx is None:
            Toast.show_success(self, "Bản nháp này đã hoàn tất 100% nội dung.")
            return

        if self.sub_editor.table.rowCount() > start_idx:
            item = self.sub_editor.table.item(start_idx, 0)
            if item:
                self.sub_editor.table.scrollToItem(item)
                self.sub_editor.table.selectRow(start_idx)

        Toast.show_info(self, f"Đã định vị đến câu {start_idx + 1}. Bạn có thể kiểm tra và bấm bắt đầu khi sẵn sàng.")

    def _switch_recovery_session(self):
        project = self.project_service.current_project
        proj_id = getattr(self.project_service, "current_project_id", None) or getattr(project, "project_id", None)
        proj_path = getattr(self.project_service, "current_project_path", None) or self.project_service.project_dir or ""
        active = getattr(self.recovery_manager, "_active_session", None)
        if active and active.manifest.project_id == proj_id and active.manifest.project_file_path == proj_path:
            return active
        if active:
            self.recovery_manager.finalize_clean_shutdown()
        source = getattr(project, "source", None)
        return self.recovery_manager.create_session(RecoveryContext(
            proj_id,
            proj_path,
            getattr(source, "path", "") if source else "",
            getattr(source, "fingerprint", "") if source else "",
            getattr(source, "modified_at", 0.0) if source else 0.0,
        ))

    def action_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec():
            data = dialog.get_project_data()
            
            import os
            safe_name = "".join(c if c.isalnum() else "_" for c in data["name"])
            full_project_dir = os.path.join(data["project_dir"], f"{safe_name}.ai-subtitle")
            
            try:
                self.project_service.create_project(full_project_dir, data["name"], data["video_path"])
                self.revision_tracker.reset_for_new_document()
                self._switch_recovery_session()
                
                self.workspace_service.restore_workspace()
                self.generation_panel.check_resumable_state()
                self._refresh_transcription_context_views()
                
                QMessageBox.information(self, "Thành công", f"Đã khởi tạo dự án: {data['name']}\nĐừng quên nhấn Ctrl+S để lưu tiến độ nhé!")
            except (OSError, ValueError, RuntimeError) as e:
                QMessageBox.critical(self, "Lỗi khởi tạo", f"Không thể tạo dự án:\n{e!s}")

    def _on_new_from_url(self):
        dialog = MediaImportDialog(self.media_import_service, self, mode="new_project")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.get_result()
        project_data = dialog.get_project_data()
        if not result or not result.local_path or not project_data:
            return
        try:
            self.project_service.create_project(
                project_data["bundle_path"], project_data["name"], result.local_path
            )
            self._queue_project_dirs[result.local_path] = project_data["bundle_path"]
            self.video_player.load_video(result.local_path)
            self.revision_tracker.reset_for_new_document()
            self._switch_recovery_session()
            self.workspace_service.restore_workspace()
            self.generation_panel.check_resumable_state()
            self._refresh_transcription_context_views()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Import Failed", f"Could not create project:\n{exc}")

    def _on_add_url_to_queue(self):
        dialog = MediaImportDialog(self.media_import_service, self, mode="queue")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.get_result()
        if not result or not result.local_path:
            return
        if not self.queue_mgr.add_video(result.local_path):
            return
        self._queue_project_dirs[result.local_path] = None
        self.queue_mgr.set_active(result.local_path)
        self.video_player.load_video(result.local_path)

    def action_save_project(self):
        if not getattr(self, 'project_service', None) or not self.project_service.current_project:
            Toast.show_info(self, "Chưa có dự án nào được mở để lưu.")
            return False
            
        try:
            # 1. Chụp lại trạng thái giao diện
            self.workspace_service.capture_workspace()
            
            # 2. ÉP GHI DỮ LIỆU TIMELINE XUỐNG ĐÚNG FILE ĐANG MỞ (PERSISTENCE)
            if hasattr(self, 'sub_editor') and self.sub_editor.all_segments:
                project = self.project_service.current_project
                
                # Tìm ID của file Artifact đang được dùng
                art_id = project.state.active_artifact_id
                if hasattr(project.state, 'timing') and getattr(project.state.timing, 'timing_artifact_id', None):
                    art_id = project.state.timing.timing_artifact_id
                    
                if art_id:
                    artifact = self.project_service.artifact_store.get(art_id)
                    if artifact and artifact.path:
                        
                        # TRƯỜNG HỢP 1: File đang mở là SRT -> Phải xuất file SRT đè lên
                        if artifact.path.lower().endswith('.srt'):
                            try:
                                from core.subtitle_exporter import SubtitleExportService
                                exporter = SubtitleExportService()
                                subs_for_export = []
                                for seg in self.sub_editor.all_segments:
                                    # Lấy thời gian từ biến số nguyên (start_ms) để chính xác tuyệt đối
                                    start_ms = int(seg.get('start_ms', self.sub_editor.time_str_to_ms(seg.get('start', '00:00:00,000'))))
                                    end_ms = int(seg.get('end_ms', self.sub_editor.time_str_to_ms(seg.get('end', '00:00:00,000'))))
                                    text = seg.get('text', '')
                                    if text == "[ Chưa có nội dung ]": text = ""
                                    subs_for_export.append((start_ms, end_ms, text))
                                    
                                exporter.export_srt(subs_for_export, artifact.path)
                                print(f"[DEBUG-SAVE] Đã ghi đè thành công Timing mới vào file SRT: {artifact.path}")
                            except (OSError, ValueError, RuntimeError) as ex:
                                print(f"[LỖI XUẤT SRT] {ex}")
                                raise
                                
                        # TRƯỜNG HỢP 2: File đang mở là Draft (.json) -> Dùng hàm lưu Draft
                        else:
                            draft_path = self.sub_editor.save_draft(silent=True)
                            if draft_path and draft_path != artifact.path:
                                artifact.path = draft_path
                                self.queue_mgr.set_srt_for_video(self.queue_mgr.active_vid, draft_path)
                                print(f"[DEBUG-SAVE] Đã cập nhật đường dẫn Artifact sang Draft mới: {draft_path}")
            
            # 3. Lưu toàn bộ nhật ký Project xuống đĩa
            result = self.project_service.save_project()
            if result is False:
                return False
            self.recovery_manager.record_explicit_save()
            self.revision_tracker.record_explicit_save_success()
            self.global_undo_manager.mark_saved()
            self._update_window_title_dirty_marker(False)
            Toast.show_success(self, f"Đã lưu dự án '{self.project_service.current_project.name}' thành công!")
            return True
            
        except (OSError, ValueError, RuntimeError) as e:
            Toast.show_error(self, f"Không thể lưu dự án:\n{e!s}")
            import traceback
            print(traceback.format_exc())
            return False

    def action_open_project(self):
        """Mở một dự án đã có (Tối ưu UX chống giật/co giãn Layout)"""
        project_dir = QFileDialog.getExistingDirectory(self, "Chọn Thư mục Dự án (.ai-subtitle)")
        if not project_dir:
            return
            
        try:
            # 1. CHUYỂN TRANG NGAY LẬP TỨC: Giấu đi thời gian chờ nạp dữ liệu
            self.switch_page(1)
            # Ép Qt vẽ xong màn hình Workspace trước khi CPU bị chặn bởi việc nạp file
            QApplication.processEvents() 

            # 2. KHÓA RENDER: Chặn UI tự động co giãn khi nhồi dữ liệu lớn vào Table/Timeline
            self.page_workspace.setUpdatesEnabled(False)

            self.project_service.open_project(project_dir)
            self.revision_tracker.reset_for_new_document()
            self._switch_recovery_session()
            source_path = self.project_service.current_project.source.path
            self._queue_project_dirs[source_path] = project_dir
            self.workspace_service.restore_workspace()
            
            # --- LẤY THỜI LƯỢNG AN TOÀN CHỐNG CRASH ---
            dur_ms = 0
            if hasattr(self, 'video_player') and hasattr(self.video_player, 'player'):
                dur_ms = self.video_player.player.duration()
                
            if dur_ms <= 0:
                vid_path = getattr(self.project_service.current_project, 'video_path', '')
                if not vid_path:
                    vid_path = self.queue_mgr.active_vid
                if vid_path and vid_path in self.queue_mgr.get_items():
                    dur_ms = int(self.queue_mgr.get_items()[vid_path].get('duration', 0) * 1000)

            if dur_ms <= 0 and self.sub_editor.all_segments:
                last_seg = self.sub_editor.all_segments[-1]
                if 'end_ms' in last_seg:
                    dur_ms = int(last_seg['end_ms']) + 5000
                else:
                    end_time_str = last_seg.get('end', '00:00:00,000') if isinstance(last_seg, dict) else '00:00:00,000'
                    dur_ms = self.sub_editor.time_str_to_ms(end_time_str) + 5000

            if dur_ms <= 0:
                dur_ms = 3600000

            # --- NẠP DỮ LIỆU ---
            self.timeline_data_provider.load_runtime_data(self.sub_editor.all_segments, dur_ms)
            self.sub_editor.render_page()
            
            waveform_data = None
            if hasattr(self.timeline_widget, 'container') and hasattr(self.timeline_widget.container, 'waveform'):
                waveform_data = getattr(self.timeline_widget.container.waveform, 'waveform_data', None)

            self.timeline_widget.load_project_data(
                dur_ms,
                self.timeline_data_provider.get_all_segments(),
                waveform_data
            )

            self.generation_panel.set_video_duration(dur_ms)
            self.generation_panel.check_resumable_state()
            self._refresh_transcription_context_views()
            
        except (OSError, ValueError, KeyError, RuntimeError) as e:
            Toast.show_error(self, f"File dự án bị hỏng hoặc không hợp lệ:\n{e!s}")
            print(f"[LỖI CRASH MỞ PROJECT] {e}")
        finally:
            # 3. MỞ KHÓA RENDER: Vẽ đồng loạt tất cả mọi thứ ra màn hình trong 1 frame duy nhất
            self.page_workspace.setUpdatesEnabled(True)
            if getattr(self.project_service, 'current_project', None):
                Toast.show_success(self, f"Đã mở dự án: {self.project_service.current_project.name}")

    def handle_ipc_request(self, request: IpcRequest) -> None:
        if request.action is IpcAction.ACTIVATE_WINDOW:
            if self.isMinimized():
                self.showNormal()
            self.raise_()
            self.activateWindow()
        elif request.action is IpcAction.OPEN_PROJECT and request.path:
            self.project_service.open_project(request.path)
            self.workspace_service.restore_workspace()
            self._refresh_transcription_context_views()
            self.activateWindow()
        elif request.action is IpcAction.OPEN_MEDIA and request.path:
            if hasattr(self, "queue_mgr"):
                self.queue_mgr.add_video(request.path)
            if hasattr(self, "video_player") and hasattr(self.video_player, "load_video"):
                self.video_player.load_video(request.path)
            self.activateWindow()

    def action_open_model_manager(self):
        from ui.dialogs.model_manager_dialog import ModelManagerDialog
        dialog = ModelManagerDialog(self)
        dialog.exec()

    def _register_artifact(self, path: str, a_type, metadata: dict | None = None) -> None:
        self.append_log(f"\n[DEBUG] Đang thử đăng ký Artifact: {path}")
        
        if not getattr(self, 'project_service', None):
            self.append_log("❌ [DEBUG] Lỗi: project_service chưa được khởi tạo.")
            return
            
        if not self.project_service.current_project:
            self.append_log("❌ [DEBUG] Lỗi: Không có Project nào đang mở trong RAM! (Vui lòng bấm Ctrl+O để mở Project trước khi thao tác).")
            return
            
        if not path:
            self.append_log("❌ [DEBUG] Lỗi: Đường dẫn file truyền vào bị rỗng.")
            return
            
        if not os.path.exists(path):
            self.append_log(f"❌ [DEBUG] Lỗi: Không tìm thấy file thực tế trên ổ cứng tại: {path}")
            return

        from core.artifacts.artifact import Artifact
        from core.artifacts.artifact_types import ArtifactStatus, ArtifactType

        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            artifact_type=a_type,
            path=path,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            source_project_id=self.project_service.current_project.project_id,
            status=ArtifactStatus.READY,
            metadata=metadata or {}
        )
        self.artifact_store.register(artifact)
        self.project_service.current_project.state.active_artifact_id = artifact.artifact_id    
        
        # --- ĐỒNG BỘ TIMING ARTIFACT ID ---
        if a_type == ArtifactType.TIMING:
            self.project_service.current_project.state.timing_status = "READY"
            if hasattr(self.project_service.current_project.state, 'timing') and self.project_service.current_project.state.timing:
                self.project_service.current_project.state.timing.timing_artifact_id = artifact.artifact_id
        elif a_type == ArtifactType.DRAFT:
            self.project_service.current_project.state.timing_status = "READY" 
            self.project_service.current_project.state.text_status = "DRAFT"
            if hasattr(self.project_service.current_project.state, 'timing') and self.project_service.current_project.state.timing:
                self.project_service.current_project.state.timing.timing_artifact_id = artifact.artifact_id
        else:
            self.project_service.current_project.state.timing_status = "READY"
            self.project_service.current_project.state.text_status = "READY"

        self.project_service.mark_dirty()
        self.append_log(f"📦 [PROJECT] Đã lưu Artifact {a_type.name}: {os.path.basename(path)}")

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
