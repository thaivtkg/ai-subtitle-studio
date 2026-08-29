import os
import re
import subprocess
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.artifacts.artifact_store import ArtifactStore
from core.Backend import is_garbage
from core.queue_manager import QueueManager
from core.services.project_service import ProjectService
from core.services.workspace_service import WorkspaceService
from core.video_metadata import MetadataWorker, VideoMetadataExtractor
from player.video_player import VideoPlayerWidget
from ui.animations.animation_types import SubtitleAppearMode, SubtitleDisappearMode
from ui.animations.subtitle_animation_controller import SubtitleTextEffect
from ui.components.animated_stack import AnimatedStack
from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.pages.ai_panel import AIGenerationPanel
from ui.pages.dashboard_page import DashboardPage
from ui.pages.draft_center_page import DraftCenterPage
from ui.pages.export_center_page import ExportCenterPage
from ui.pages.settings_page import SettingsCenterPage
from ui.queue_widget import QueueWidget
from ui.SubEditor import SubtitleEditorWidget
from ui.theme import Theme
from ui.toast import Toast
from utils import load_settings, save_settings
from workers.TaskQueue import FillTextWorker, HardsubWorker, WhisperWorker



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

    def __init__(self):
        super().__init__()

        # Lắng nghe Signal vẽ sóng âm từ luồng phụ gửi lên
        self.waveform_ready_signal.connect(self._on_waveform_ready_slot)

        # --- KHỞI TẠO HỆ THỐNG PROJECT (SPRINT 7) ---
        self.artifact_store = ArtifactStore()
        self.project_service = ProjectService(self.artifact_store)
        self.workspace_service = WorkspaceService(self, self.project_service)

        # --- [SPRINT 7.1] TIMING BATCH SERVICE ---
        from core.timing.timing_batch_service import TimingBatchService
        self.timing_service = TimingBatchService(self.project_service)
        self.timing_service.progress_signal.connect(self.update_progress)
        self.timing_service.log_signal.connect(self.append_log)
        self.timing_service.batch_completed_signal.connect(self._on_timing_batch_completed)
        self.timing_service.timing_finished_signal.connect(self._on_timing_finished)
        self.timing_service.state_changed_signal.connect(self._on_timing_state_changed)
        self.timing_service.error_signal.connect(self._on_timing_error)
        # -----------------------------------------

        # Phím tắt Dự án (Gắn cờ ApplicationShortcut để chống mất Focus)
        self.shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self.shortcut_new.setContext(Qt.ApplicationShortcut)
        self.shortcut_new.activated.connect(self.action_new_project)
        
        self.shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self.shortcut_open.setContext(Qt.ApplicationShortcut)
        self.shortcut_open.activated.connect(self.action_open_project)

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.setContext(Qt.ApplicationShortcut)
        self.shortcut_save.activated.connect(self.action_save_project)
        
        self.setWindowTitle("AI Subtitle Studio")
        
        self.setMinimumSize(1280, 720)
        self.resize(1366, 768)
        self.center_on_screen()
        self.setStyleSheet(Theme.get_global_stylesheet())
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.old_pos = QPoint()

        self.queue_mgr = QueueManager()
        self.queue_mgr.queue_updated.connect(self.on_queue_updated)
        self.queue_mgr.active_changed.connect(
            lambda vid: self.queue_ui.sync_with_manager(self.queue_mgr.get_items(), vid) if hasattr(self, 'queue_ui') else None
        )
        self.queue_mgr.item_removed.connect(self.on_queue_item_removed_handler)
        self.setAcceptDrops(True)

        root_widget = QWidget()
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

        # Splitter dọc (Vertical) định hình 3 tầng cốt lõi
        self.work_splitter = QSplitter(Qt.Vertical)
        self.work_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; height: 2px; }}")

        # --- TẦNG 1: VIDEO PREVIEW ---
        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(200)
        self.work_splitter.addWidget(self.video_player)

        # --- TẦNG 2: SUBTITLE EDITOR & AI SIDE-PANEL ---
        self.editor_horizontal_splitter = QSplitter(Qt.Horizontal)
        self.editor_horizontal_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; width: 2px; }}")

        # 2.1 Bảng Editor Chính (Bên trái)
        self.sub_editor = SubtitleEditorWidget()
        self.sub_editor.seek_requested.connect(self.video_player.set_position)
        self.video_player.sub_controller.subtitle_cleared.connect(self.sub_editor.clear_highlight)
        self.video_player.sub_controller.subtitle_changed.connect(
            lambda stt, start, text: self.sub_editor.highlight_row_by_stt(stt)
        )
        self.sub_editor.preview_toggled.connect(self.video_player.sub_controller.toggle_preview)
        self.sub_editor.style_changed.connect(
            lambda s: self.video_player.subtitle_overlay.update_style(
                family=s.get("family"), size=s.get("size"), color=s.get("color"),
                out_color=s.get("out_color"), out_width=s.get("out_width"), position=s.get("position")
            )
        )
        self.sub_editor.live_edit_applied.connect(self.video_player.sub_controller.update_live_data)
        self.sub_editor.live_edit_applied.connect(lambda *args: self.project_service.mark_dirty() if getattr(self, 'project_service', None) else None)
        self.sub_editor.fill_text_requested.connect(self.start_fill_text_worker)
        
        self.editor_horizontal_splitter.addWidget(self.sub_editor)

        # 2.2 Side-Panel cho AI & Live Log (Bên phải - Dễ dàng Collapse sau này)
        self.side_panel_tabs = QTabWidget()
        self.side_panel_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Theme.BORDER}; background: {Theme.SURFACE}; }}
            QTabBar::tab {{ background: {Theme.BG_APP}; color: {Theme.TEXT_MUTED}; padding: 6px 16px; border: 1px solid {Theme.BORDER}; border-bottom: none; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {Theme.PRIMARY_PURPLE}; color: #FFFFFF; }}
        """)
        
        self.ai_panel = AIGenerationPanel()
        self.ai_panel.start_requested.connect(self._on_ai_start_clicked)
        self.ai_panel.continue_requested.connect(self._on_ai_continue_clicked)
        self.ai_panel.cancel_requested.connect(self._on_ai_cancel_clicked)
        self.ai_panel.retry_requested.connect(self._on_ai_retry_clicked)
        self.side_panel_tabs.addTab(self.ai_panel, "🤖 AI Actions")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái...")
        self.side_panel_tabs.addTab(self.log_box, "📜 Live Log")

        self.editor_horizontal_splitter.addWidget(self.side_panel_tabs)
        # Đặt tỷ lệ: Editor chiếm 70% không gian ngang, AI Panel ép sang mép 30%
        self.editor_horizontal_splitter.setSizes([850, 150]) 
        
        self.work_splitter.addWidget(self.editor_horizontal_splitter)

        # --- TẦNG 3: TIMELINE & WAVEFORM ---
        from ui.timeline.timeline_widget import TimelineWidget
        from core.timeline.timeline_controller import TimelineController
        from core.timeline.timeline_integration import TimelineVideoSync
        from core.timeline.timeline_data_provider import TimelineDataProvider

        self.timeline_widget = TimelineWidget()
        self.timeline_widget.setMinimumHeight(160) # Timeline nay đã nằm dưới cùng, chiếm ưu thế
        self.work_splitter.addWidget(self.timeline_widget)

        self.timeline_data_provider = TimelineDataProvider()
        self.timeline_controller = TimelineController(self.project_service, self.timeline_widget, self.timeline_data_provider)
        self.video_sync = TimelineVideoSync(self.video_player, self.timeline_widget, self.timeline_controller.state_manager)
        
        # Liên kết Cầu đồng bộ (Click Table -> Bôi đen Timeline)
        self.sub_editor.seek_requested.connect(self.timeline_controller.sync_from_editor)

        # Chốt tỷ lệ 3 tầng dọc: Video (25%), Editor (55%), Timeline (20%)
        self.work_splitter.setSizes([250, 550, 200])
        ws_layout.addWidget(self.work_splitter)
        
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

        self.ai_panel.batch_spin.valueChanged.connect(self.sub_editor.spin_batch.setValue)
        self.sub_editor.spin_batch.valueChanged.connect(self.ai_panel.batch_spin.setValue)

        self.page_drafts.continue_draft_requested.connect(self._continue_draft_from_center)

        self.stack.addWidget(self.page_drafts)

        # Page 5 (Index 4): Export Center
        self.page_export = ExportCenterPage()
        self.page_export.export_srt_requested.connect(self._trigger_export_softsub)
        self.ai_panel.retry_requested.connect(self._retry_current_task)
        self.page_export.burn_hardsub_requested.connect(self._trigger_export_hardsub)
        self.stack.addWidget(self.page_export)

        # Page 6 (Index 5): Settings Center
        self.page_settings = SettingsCenterPage()
        self.page_settings.motion_preset_combo.currentIndexChanged.connect(self.on_motion_preset_changed)
        self.page_settings.appear_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.page_settings.disappear_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.page_settings.text_effect_combo.currentIndexChanged.connect(self.apply_motion_config_to_player)
        self.stack.addWidget(self.page_settings)

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
        root_layout.addWidget(right_area)

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
        self.sub_editor.emit_style()

    # --- HÀM THỰC THI SIGNAL AN TOÀN TRÊN MAIN THREAD ---
    def _on_waveform_ready_slot(self, req_vid_path, duration_ms, peaks):
        if req_vid_path != self.queue_mgr.active_vid:
            print(f"[DEBUG-WAVEFORM] Bỏ qua kết quả cũ của worker do người dùng đã chuyển video: {req_vid_path}")
            return

        try:
            # 3. [FIX REVIEW 1] Nạp Data Provider SAU KHI cả SRT và Sóng âm đã sẵn sàng trên Main Thread
            self.timeline_data_provider.load_runtime_data(self.sub_editor.all_segments, duration_ms)

            self.timeline_widget.load_project_data(
                duration_ms,
                self.timeline_data_provider.get_all_segments(),
                peaks
            )
            print("[DEBUG-WAVEFORM] 7. Vẽ Timeline UI thành công!")
        except Exception as e:
            print(f"[DEBUG-WAVEFORM] ❌ LỖI KHI VẼ UI: {e}")

    def center_on_screen(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        x = screen_geo.left() + (screen_geo.width() - self.width()) // 2
        y = screen_geo.top() + (screen_geo.height() - self.height()) // 2
        self.move(x, y)

    def create_nav_button(self, text, page_index):
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {Theme.TEXT_SECONDARY}; text-align: left; padding-left: 10px; border-radius: 6px; font-weight: 600; font-size: 12px; border: none; }} QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}")
        btn.clicked.connect(lambda: self.switch_page(page_index))
        self.nav_btns[page_index] = btn
        return btn

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
            default_dir = self.out_input.text().strip() or (os.path.dirname(list(self.queue_mgr.get_items().keys())[0]) if self.queue_mgr.get_items() else "")
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
            self.on_queue_item_clicked(added[-1])

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

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
        if "ai_mode" in s:
            idx = self.ai_panel.mode_combo.findData(s["ai_mode"])
            if idx >= 0: self.ai_panel.mode_combo.setCurrentIndex(idx)
        if "prompt" in s:
            self.ai_panel.prompt_edit.setText(s["prompt"])

    def on_motion_preset_changed(self):
        preset = self.page_settings.motion_preset_combo.currentData()
        
        self.page_settings.appear_combo.blockSignals(True)
        self.page_settings.disappear_combo.blockSignals(True)
        self.page_settings.text_effect_combo.blockSignals(True)

        if preset == "minimal":
            self.page_settings.appear_combo.setCurrentIndex(self.page_settings.appear_combo.findData("fade"))
            self.page_settings.disappear_combo.setCurrentIndex(self.page_settings.disappear_combo.findData("fade"))
            self.page_settings.text_effect_combo.setCurrentIndex(self.page_settings.text_effect_combo.findData("normal"))
        elif preset == "standard":
            self.page_settings.appear_combo.setCurrentIndex(self.page_settings.appear_combo.findData("fade"))
            self.page_settings.disappear_combo.setCurrentIndex(self.page_settings.disappear_combo.findData("fade"))
            self.page_settings.text_effect_combo.setCurrentIndex(self.page_settings.text_effect_combo.findData("normal"))
        elif preset == "dynamic":
            self.page_settings.appear_combo.setCurrentIndex(self.page_settings.appear_combo.findData("rise"))
            self.page_settings.disappear_combo.setCurrentIndex(self.page_settings.disappear_combo.findData("drop"))
            self.page_settings.text_effect_combo.setCurrentIndex(self.page_settings.text_effect_combo.findData("highlight"))
        elif preset == "off":
            self.page_settings.appear_combo.setCurrentIndex(self.page_settings.appear_combo.findData("instant"))
            self.page_settings.disappear_combo.setCurrentIndex(self.page_settings.disappear_combo.findData("instant"))
            self.page_settings.text_effect_combo.setCurrentIndex(self.page_settings.text_effect_combo.findData("normal"))

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
        except Exception:
            gpu_name, vram_str = "RTX GPU", "--"

        self.page_dashboard.update_hardware(gpu_name, vram_str, self.page_dashboard.card_cpu_val.text(), self.page_dashboard.card_status_val.text())

    def update_cpu_usage(self):
        try:
            import psutil
            cpu_str = f"{psutil.cpu_percent(interval=None):.1f}%"
            self.page_dashboard.card_cpu_val.setText(cpu_str)
        except Exception:
            pass

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
            if added: self.on_queue_item_clicked(added[-1])

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

    def on_queue_item_clicked(self, vid_path):
        self.queue_mgr.set_active(vid_path)
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
        import threading

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
                except Exception as e:
                    print(f"[DEBUG-WAVEFORM] ❌ LỖI Trích xuất sóng âm: {e}")

                if duration_ms <= 0 and peaks is not None and len(peaks) > 0:
                    duration_ms = int((len(peaks) / 100.0) * 1000)
                
                if duration_ms <= 0:
                    duration_ms = 3600000 

                # Báo cáo kết quả về Main Thread
                self.waveform_ready_signal.emit(vid_path, duration_ms, peaks)
                
            except Exception as e:
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
        for vid in self.queue_mgr.get_items().keys():
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
            self.project_service.mark_dirty()

        Toast.show_success(self, f"Render Hardsub xong: {path}")
        self.progress_bar.setValue(100)
        self.page_dashboard.quick_progress.setValue(100)
        QTimer.singleShot(2500, self._cleanup_ui_after_task)

    def _on_manual_hardsub_error(self, err):
        Toast.show_error(self, f"Lỗi Hardsub: {err}")
        self._cleanup_ui_after_task()

    def start_processing(self):
        items = self.queue_mgr.get_items()
        if not items: return
        self.is_cancelled_flag = False
        self.batch_queue = [(vid, data.get("srt_path")) for vid, data in items.items()]
        self.total_batch_items = len(self.batch_queue)
        self.current_batch_index = 0
        self.output_dir = self.out_input.text().strip()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.ai_panel.set_state("PROCESSING", "Đang khởi chạy luồng AI...")
        self.page_dashboard.card_status_val.setText("Processing")
        self.log_box.clear()
        self.process_next_batch_item()

    def process_next_batch_item(self):
        if self.is_cancelled_flag or not hasattr(self, 'batch_queue') or len(self.batch_queue) == 0:
            if not self.is_cancelled_flag:
                self.process_finished("Toàn bộ tiến trình đã hoàn tất!")
            return

        self.current_batch_index += 1
        self.current_vid, current_srt = self.batch_queue.pop(0)
        file_name = os.path.basename(self.current_vid)

        self.append_log(f"\n==================================================")
        self.append_log(f"🎬 ĐANG XỬ LÝ [{self.current_batch_index}/{self.total_batch_items}]: {file_name}")
        self.append_log(f"==================================================")

        self.on_queue_item_clicked(self.current_vid)

        if not current_srt:
            if self.ai_panel.mode_combo.currentData() == "timing":
                self.append_log("[AI] Bắt đầu chế độ Timing Only (Chỉ trích xuất thời gian).")
                self.append_log("[AI] Đang chạy thuật toán VAD (Silero) để phân tách giọng nói...")
                self.append_log("[AI] Quá trình này chạy ngầm và rất nhanh, vui lòng đợi...")
            
            if getattr(self, 'project_service', None) and self.project_service.current_project:
                worker_out_dir = os.path.join(self.project_service.project_dir, "artifacts")
                os.makedirs(worker_out_dir, exist_ok=True)
            else:
                worker_out_dir = self.output_dir

            self.worker = WhisperWorker(
                video_path=self.current_vid,
                output_dir=worker_out_dir, 
                initial_prompt=self.ai_panel.prompt_edit.text().strip(),
                compute_type=self.page_settings.compute_combo.currentData(),
                use_vad=self.page_settings.chk_vad.isChecked(),
                min_silence_ms=self.page_settings.silence_spin.value(), 
                model_size=self.page_settings.model_combo.currentData(),
                generation_mode=self.ai_panel.mode_combo.currentData()
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_whisper_finished)
            self.worker.error_signal.connect(self.process_error)
            self.worker.start()
        else:
            if current_srt.endswith('.ai-subtitle-draft'):
                self.append_log("❌ File Draft cần được lưu thành SRT trước khi Hardsub.")
                self.process_next_batch_item()
                return

            if not self.page_settings.chk_hardsub_enable.isChecked():
                self.append_log("[HỆ THỐNG] Hardsub tự động đang tắt. Bỏ qua Hardsub cho video hiện tại.")
                self.process_next_batch_item()
                return

            self.worker = HardsubWorker(
                video_path=self.current_vid,
                srt_path=current_srt,
                output_dir=self.output_dir,
                font_size=self.page_settings.size_spin.value(),
                font_color="white",
                font_name=self.page_settings.font_combo.currentText()
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_hardsub_finished)
            self.worker.error_signal.connect(self.process_error)
            self.worker.start()

    def on_whisper_finished(self, msg, srt_path):
        self.append_log(f"[AI] {msg}")
        self.queue_mgr.set_srt_for_video(self.current_vid, srt_path)
        
        if getattr(self, 'project_service', None) and self.project_service.current_project and srt_path and os.path.exists(srt_path):
            import uuid
            from datetime import datetime
            from core.artifacts.artifact import Artifact
            from core.artifacts.artifact_types import ArtifactType, ArtifactStatus
            
            run_mode = self.ai_panel.mode_combo.currentData()
            
            if run_mode == "timing":
                a_type = ArtifactType.TIMING
            elif srt_path.endswith('.ai-subtitle-draft'):
                a_type = ArtifactType.DRAFT
            else:
                a_type = ArtifactType.SUBTITLE
                
            artifact = Artifact(
                artifact_id=str(uuid.uuid4()),
                artifact_type=a_type,
                path=srt_path,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source_project_id=self.project_service.current_project.project_id,
                status=ArtifactStatus.READY
            )
            
            self.artifact_store.register(artifact)
            self.project_service.current_project.state.active_artifact_id = artifact.artifact_id
            
            if a_type == ArtifactType.TIMING:
                self.project_service.current_project.state.timing_status = "READY"
            elif a_type == ArtifactType.DRAFT:
                self.project_service.current_project.state.timing_status = "READY" 
                self.project_service.current_project.state.text_status = "DRAFT"
            else:
                self.project_service.current_project.state.timing_status = "READY"
                self.project_service.current_project.state.text_status = "READY"
                
            self.project_service.mark_dirty()
            self.append_log(f"📦 [PROJECT] Đã lưu Artifact {a_type.name} vào dữ liệu dự án.")
        
        if self.ai_panel.mode_combo.currentData() == "timing":
            if srt_path and os.path.exists(srt_path):
                if srt_path.endswith('.ai-subtitle-draft'):
                    self.sub_editor.load_draft_file(srt_path)
                else:
                    self.sub_editor.load_srt_file(srt_path)
                self.video_player.sub_controller.load_srt(srt_path)
            
            self.switch_page(1)
            self.bottom_tabs.setCurrentIndex(0)
            self.process_finished("Đã tạo Timing Draft thành công!")
            return
            
        if not self.page_settings.chk_hardsub_enable.isChecked():
            self.append_log("[HỆ THỐNG] Hardsub tự động đang tắt. Chuyển sang xử lý tiếp theo...")
            self.process_next_batch_item()
            return

        from ui.hardsub_confirm_dialog import HardsubConfirmDialog
        dlg = HardsubConfirmDialog(self.current_vid, self)
        dlg.exec()
        if dlg.user_choice == HardsubConfirmDialog.HARDSUB:
            out_dir = self.page_export.out_edit.text().strip() or self.out_input.text().strip()
            self.worker = HardsubWorker(
                video_path=self.current_vid,
                srt_path=srt_path,
                output_dir=out_dir,
                font_size=self.page_settings.size_spin.value(),
                font_color="white",
                font_name=self.page_settings.font_combo.currentText()
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_hardsub_finished)
            self.worker.error_signal.connect(self.process_error)
            self.worker.start()
        else:
            self.process_next_batch_item()

    def on_hardsub_finished(self, msg, out_video_path):
        from core.artifacts.artifact_types import ArtifactType
        self._register_artifact(out_video_path, ArtifactType.HARDSUB, {"mode": "auto_queue_hardsub"})
        if getattr(self, 'project_service', None) and self.project_service.current_project:
            self.project_service.current_project.state.export_status = "READY"
            self.project_service.mark_dirty()

        self.append_log(f"[FFmpeg] Xuất file thành công: {out_video_path}")
        self.process_next_batch_item()

    def cancel_processing(self):
        self.is_cancelled_flag = True
        self.batch_queue = []
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("[HỆ THỐNG] Đang dừng an toàn...")
            self.cancel_btn.setEnabled(False)

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
        self.ai_panel.progress_bar.setValue(val)
        if msg:
            self.lbl_speed_eta.setText(msg)
            self.ai_panel.lbl_step_info.setText(msg)

    def append_log(self, msg):
        self.log_box.append(msg)
        self.page_dashboard.activity_log.append(msg)
        speed_match = re.search(r"speed=\s*([0-9\.]+x)", msg)
        if speed_match:
            self.lbl_speed_eta.setText(f"Speed: {speed_match.group(1)}")

    def process_finished(self, msg):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.ai_panel.set_state("COMPLETED", msg)
        self.page_dashboard.card_status_val.setText("Idle")
        self.progress_anim.stop()
        self.progress_bar.setValue(0)
        
        self.page_dashboard.quick_progress.setValue(0) 
        
        self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
        Toast.show_success(self, msg)

        self._cleanup_ui_after_task()

    def process_error(self, err):
        self.append_log(f"❌ [LỖI] {err}")
        self.ai_panel.set_state("ERROR", str(err))

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
        self.ai_panel.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
        self.page_dashboard.card_status_val.setText("Idle")

    def open_output_folder(self):
        out_d = self.out_input.text().strip() or (os.path.dirname(list(self.queue_mgr.get_items().keys())[0]) if self.queue_mgr.get_items() else "")
        if out_d and os.path.exists(out_d):
            os.startfile(out_d)

    def start_fill_text_worker(self, start_idx, count):
        if not self.queue_mgr.active_vid:
            Toast.show_info(self, "Vui lòng chọn video để điền chữ.")
            return

        actual_count = self.ai_panel.batch_spin.value()
        target_segs = self.sub_editor.all_segments[start_idx : start_idx + actual_count]
        segments_for_ai = []
        for s in target_segs:
            s_ms = self.sub_editor.time_str_to_ms(s['start'])
            e_ms = self.sub_editor.time_str_to_ms(s['end'])
            raw = s['text'] if s['text'] != "[ Chưa có nội dung ]" else ""
            stt = int(s['stt']) if str(s['stt']).isdigit() else 0
            segments_for_ai.append((s_ms, e_ms, raw, stt))

        if not segments_for_ai:
            Toast.show_info(self, "Không có đoạn nào cần điền chữ.")
            return

        self.append_log(f"\n==================================================")
        self.append_log(f"🤖 BẮT ĐẦU ĐIỀN CHỮ AI [Câu {start_idx + 1} đến {start_idx + len(segments_for_ai)}]")
        self.append_log(f"==================================================")
        self.append_log(f"[AI] Đang nạp Audio và Model ({self.page_settings.model_combo.currentData()}) vào VRAM...")
        self.append_log(f"[AI] Quá trình infer có thể mất vài giây im lặng, vui lòng không tắt ứng dụng...")
        self.progress_bar.setValue(0)
        self.ai_panel.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("Đang khởi động AI Batch...")
        self.ai_panel.set_state("PROCESSING", f"Đang điền câu {start_idx + 1} - {start_idx + len(segments_for_ai)}...")

        self.ai_panel.lbl_batch_stat.setText(f"Batch Progress: Đang xử lý {len(segments_for_ai)} segments...")

        self.is_cancelled_flag = False
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = FillTextWorker(
            video_path=self.queue_mgr.active_vid,
            segments_data=segments_for_ai,
            initial_prompt=self.ai_panel.prompt_edit.text().strip(),
            compute_type=self.page_settings.compute_combo.currentData(),
            model_size=self.page_settings.model_combo.currentData()
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_fill_text_finished)
        self.worker.error_signal.connect(self.process_error)
        self.worker.start()

    def on_fill_text_finished(self, filled_segments):
        for start_ms, end_ms, text, stt in filled_segments:
            for seg in self.sub_editor.all_segments:
                if str(seg['stt']) == str(stt):
                    seg['text'] = text
                    seg['status'] = 'draft'
                    break

        self.sub_editor.render_page()
        self.sub_editor.update_draft_progress()

        draft_file = self.sub_editor.save_draft(silent=True)
        if draft_file:
            self.queue_mgr.set_srt_for_video(self.queue_mgr.active_vid, draft_file)

        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.ai_panel.set_state("COMPLETED", "Điền chữ hoàn tất!")

        self.ai_panel.lbl_batch_stat.setText(f"Batch Progress: Hoàn tất {len(filled_segments)} segments")
        
        self.progress_bar.setValue(100)
        self.ai_panel.progress_bar.setValue(100)
        QTimer.singleShot(2500, self._reset_progress_state)
        
        Toast.show_success(self, "Đã điền chữ AI hoàn tất lượt Batch!")

    def _reset_progress_state(self):
        if not hasattr(self, 'worker') or not self.worker.isRunning():
            self.progress_bar.setValue(0)
            self.ai_panel.progress_bar.setValue(0)
            self.page_dashboard.quick_progress.setValue(0) 
            
            self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
            if self.ai_panel.state == "COMPLETED":
                self.ai_panel.set_state("READY", "Sẵn sàng cho tác vụ tiếp theo")   

    def closeEvent(self, event):
        if getattr(self, 'project_service', None) and self.project_service.current_project:
            self.workspace_service.capture_workspace()
            
            if self.project_service.current_project.state.dirty:
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, 
                    "Lưu thay đổi?", 
                    f"Dự án '{self.project_service.current_project.name}' có thay đổi chưa được lưu.\nBạn có muốn lưu lại trước khi thoát không?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save
                )
                
                if reply == QMessageBox.Save:
                    self.action_save_project()
                elif reply == QMessageBox.Cancel:
                    event.ignore()  
                    return

        save_settings({
            "output_dir": self.out_input.text().strip(),
            "model_size": self.page_settings.model_combo.currentData(),
            "compute_type": self.page_settings.compute_combo.currentData(),
            "use_vad": self.page_settings.chk_vad.isChecked(),
            "min_silence_ms": self.page_settings.silence_spin.value(),
            "do_hardsub": self.page_settings.chk_hardsub_enable.isChecked(),
            "font_name": self.page_settings.font_combo.currentText(),
            "font_size": self.page_settings.size_spin.value(),
            "ai_mode": self.ai_panel.mode_combo.currentData(),
            "prompt": self.ai_panel.prompt_edit.text().strip()
        })
        
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
            
        try:
            import os, subprocess
            if os.name == 'nt':
                subprocess.Popen(["taskkill", "/f", "/im", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
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
        except Exception as e:
            Toast.show_error(self, f"Lỗi hệ thống tập tin: {str(e)}")
            return

        base_name = os.path.splitext(os.path.basename(self.queue_mgr.active_vid))[0]
        exported = []

        try:
            from core.subtitle_exporter import SubtitleExportService
            from core.artifacts.artifact_types import ArtifactType
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
                    self.project_service.mark_dirty()
                Toast.show_success(self, f"Đã xuất thành công: {', '.join(exported)}")
            else:
                Toast.show_info(self, "Vui lòng chọn ít nhất một định dạng xuất.")
        except Exception as e:
            Toast.show_error(self, f"Lỗi trong quá trình ghi file: {str(e)}")

    # ==========================================================
    # [SPRINT 7.1] ĐIỀU PHỐI AI & TIMING BATCH UI
    # ==========================================================
    def _get_current_ai_settings(self):
        return {
            "model_size": self.page_settings.model_combo.currentData(),
            "compute_type": self.page_settings.compute_combo.currentData(),
            "use_vad": self.page_settings.chk_vad.isChecked(),
            "min_silence_ms": self.page_settings.silence_spin.value()
        }

    def _find_first_empty_segment(self):
        """Hàm phụ trợ: Quét tìm câu phụ đề trống đầu tiên để điền chữ"""
        for i, seg in enumerate(self.sub_editor.all_segments):
            text = str(seg.get('text', '')).strip()
            if not text or text == "[ Chưa có nội dung ]":
                return i
        return None

    def _on_ai_start_clicked(self):
        self.setFocus() 
        mode = self.ai_panel.mode_combo.currentData()
        
        if mode == "timing":
            try:
                batch_size = int(self.ai_panel.batch_combo.currentText())
                self.timing_service.start_timing(batch_size, self._get_current_ai_settings())
            except Exception as e:
                Toast.show_error(self, str(e))
                
        elif mode == "fill_text":
            # Điều hướng chính xác vào luồng Fill Text
            start_idx = self._find_first_empty_segment()
            if start_idx is not None:
                self.start_fill_text_worker(start_idx, 0)
            else:
                Toast.show_success(self, "Tất cả các câu đã được điền chữ!")
                
        else:
            self.start_processing()

    def _on_ai_continue_clicked(self):
        self.setFocus()
        mode = self.ai_panel.mode_combo.currentData()
        
        if mode == "timing":
            try:
                batch_size = int(self.ai_panel.batch_combo.currentText())
                self.timing_service.continue_timing(batch_size, self._get_current_ai_settings())
            except Exception as e:
                Toast.show_error(self, str(e))
                
        elif mode == "fill_text":
            start_idx = self._find_first_empty_segment()
            if start_idx is not None:
                self.start_fill_text_worker(start_idx, 0)
            else:
                Toast.show_success(self, "Tất cả các câu đã được điền chữ!")
                
        else:
            self.start_processing()

    def _on_ai_cancel_clicked(self):
        mode = self.ai_panel.mode_combo.currentData()
        if mode == "timing":
            self.timing_service.cancel_timing()
        else:
            # Dùng chung hàm cancel cho cả Fill Text và Transcribe
            self.cancel_processing()

    def _on_ai_retry_clicked(self):
        mode = self.ai_panel.mode_combo.currentData()
        if mode == "timing":
            try:
                batch_size = int(self.ai_panel.batch_combo.currentText())
                self.timing_service.retry_timing(batch_size, self._get_current_ai_settings())
            except Exception as e:
                Toast.show_error(self, str(e))
                
        elif mode == "fill_text":
            start_idx = self._find_first_empty_segment()
            if start_idx is not None:
                self.start_fill_text_worker(start_idx, 0)
            else:
                Toast.show_success(self, "Tất cả các câu đã được điền chữ!")
                
        else:
            self._retry_current_task()

    def _on_timing_state_changed(self, status, msg):
        self.ai_panel.set_state("PROCESSING" if status == "RUNNING" else status, msg)
        self.page_dashboard.card_status_val.setText(status)
        
        if status in ["READY", "IDLE", "COMPLETED", "FAILED"]:
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.page_dashboard.quick_progress.setValue(0)
        else:
            self.start_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            
        self.update_timing_ui_info()

    def _on_timing_batch_completed(self, added_count, batch_size):
        project = self.project_service.current_project
        if project and project.state.active_artifact_id:
            art = self.project_service.artifact_store.get(project.state.active_artifact_id)
            if art and os.path.exists(art.path):
                if art.path.endswith('.ai-subtitle-draft'):
                    self.sub_editor.load_draft_file(art.path)
                else:
                    self.sub_editor.load_srt_file(art.path)
                self.video_player.sub_controller.load_srt(art.path)
                
                last_idx = self.sub_editor.table.rowCount() - 1
                if last_idx >= 0:
                    item = self.sub_editor.table.item(last_idx, 0)
                    if item:
                        self.sub_editor.table.scrollToItem(item)
                        self.sub_editor.table.selectRow(last_idx)

        Toast.show_success(self, f"Đã hoàn thành Batch ({added_count} câu)!")
        self.update_timing_ui_info()
        
        self.progress_bar.setValue(100)
        self.ai_panel.progress_bar.setValue(100)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, self._reset_progress_state_timing)

    def _reset_progress_state_timing(self):
        project = self.project_service.current_project
        if project and project.state.timing.status in ["IDLE", "READY", "COMPLETED"]:
            from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
            
            self._progress_anim_group = QParallelAnimationGroup(self)
            
            bars = [self.progress_bar, self.ai_panel.progress_bar, self.page_dashboard.quick_progress]
            for bar in bars:
                anim = QPropertyAnimation(bar, b"value")
                anim.setDuration(800) 
                anim.setStartValue(100)
                anim.setEndValue(0)
                anim.setEasingCurve(QEasingCurve.InOutQuad) 
                self._progress_anim_group.addAnimation(anim)
                
            self._progress_anim_group.start()

    def _on_timing_finished(self):
        Toast.show_success(self, "Đã hoàn thành toàn bộ Video!")
        self.update_timing_ui_info()

    def _on_timing_error(self, err):
        Toast.show_error(self, f"Lỗi Timing: {err}")
        self.append_log(f"❌ [LỖI TIMING] {err}")
        self.update_timing_ui_info()

    def update_timing_ui_info(self):
        project = self.project_service.current_project
        if project:
            t_state = project.state.timing
            chk = self.project_service.load_timing_checkpoint()
            last_ms = chk.last_completed_end_ms if chk else 0
            time_str = self.timing_service._ms_to_time_str(last_ms)
            
            info = f"Đã xong: {t_state.completed_until} câu | Tiếp theo: {t_state.next_segment_index} | Trục T: {time_str}"
            self.ai_panel.lbl_checkpoint_info.setText(info)
            
            idx = self.ai_panel.batch_combo.findText(str(t_state.batch_size))
            if idx >= 0:
                self.ai_panel.batch_combo.setCurrentIndex(idx)

    def _retry_current_task(self):
        self.ai_panel.set_state("READY", "Đang thử lại...")
        if hasattr(self, 'current_batch_index') and self.current_batch_index > 0:
            self.current_batch_index -= 1
            self.batch_queue.insert(0, (self.current_vid, self.queue_mgr.get_items()[self.current_vid].get("srt_path")))
            self.process_next_batch_item()
        elif hasattr(self, 'queue_mgr') and self.queue_mgr.active_vid:
            self.start_processing()

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

    def action_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec():
            data = dialog.get_project_data()
            
            import os
            safe_name = "".join(c if c.isalnum() else "_" for c in data["name"])
            full_project_dir = os.path.join(data["project_dir"], f"{safe_name}.ai-subtitle")
            
            try:
                self.project_service.create_project(full_project_dir, data["name"], data["video_path"])
                
                self.workspace_service.restore_workspace()
                
                QMessageBox.information(self, "Thành công", f"Đã khởi tạo dự án: {data['name']}\nĐừng quên nhấn Ctrl+S để lưu tiến độ nhé!")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi khởi tạo", f"Không thể tạo dự án:\n{str(e)}")

    def action_save_project(self):
        if not getattr(self, 'project_service', None) or not self.project_service.current_project:
            Toast.show_info(self, "Chưa có dự án nào được mở để lưu.")
            return
            
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
                            except Exception as ex:
                                print(f"[LỖI XUẤT SRT] {ex}")
                                
                        # TRƯỜNG HỢP 2: File đang mở là Draft (.json) -> Dùng hàm lưu Draft
                        else:
                            draft_path = self.sub_editor.save_draft(silent=True)
                            if draft_path and draft_path != artifact.path:
                                artifact.path = draft_path
                                self.queue_mgr.set_srt_for_video(self.queue_mgr.active_vid, draft_path)
                                print(f"[DEBUG-SAVE] Đã cập nhật đường dẫn Artifact sang Draft mới: {draft_path}")
            
            # 3. Lưu toàn bộ nhật ký Project xuống đĩa
            self.project_service.save_project()
            Toast.show_success(self, f"Đã lưu dự án '{self.project_service.current_project.name}' thành công!")
            
        except Exception as e:
            Toast.show_error(self, f"Không thể lưu dự án:\n{str(e)}")
            import traceback
            print(traceback.format_exc())

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

            self.update_timing_ui_info()
            
        except Exception as e:
            Toast.show_error(self, f"File dự án bị hỏng hoặc không hợp lệ:\n{str(e)}")
            print(f"[LỖI CRASH MỞ PROJECT] {e}")
        finally:
            # 3. MỞ KHÓA RENDER: Vẽ đồng loạt tất cả mọi thứ ra màn hình trong 1 frame duy nhất
            self.page_workspace.setUpdatesEnabled(True)
            if getattr(self.project_service, 'current_project', None):
                Toast.show_success(self, f"Đã mở dự án: {self.project_service.current_project.name}")

    def action_open_model_manager(self):
        from ui.dialogs.model_manager_dialog import ModelManagerDialog
        dialog = ModelManagerDialog(self)
        dialog.exec()

    def _register_artifact(self, path: str, a_type, metadata: dict = None) -> None:
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
            
        import os
        if not os.path.exists(path):
            self.append_log(f"❌ [DEBUG] Lỗi: Không tìm thấy file thực tế trên ổ cứng tại: {path}")
            return

        import uuid
        from datetime import datetime
        from core.artifacts.artifact import Artifact
        from core.artifacts.artifact_types import ArtifactStatus, ArtifactType

        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            artifact_type=a_type,
            path=path,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
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