import os
import re
import subprocess
import sys

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.Backend import is_garbage
from core.queue_manager import QueueManager
from core.video_metadata import MetadataWorker, VideoMetadataExtractor
from player.video_player import VideoPlayerWidget
from ui.queue_widget import QueueWidget
from ui.SubEditor import SubtitleEditorWidget
from ui.theme import Theme
from ui.toast import Toast
from utils import load_settings, save_settings
from workers.TaskQueue import FillTextWorker, HardsubWorker, WhisperWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Subtitle Studio")
        self.setMinimumSize(1280, 768)
        self.resize(1366, 820)
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

        # ========================================================
        # 1. ROOT LAYOUT (MAIN APP SHELL)
        # ========================================================
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ========================================================
        # 2. LEFT SIDEBAR NAVIGATION
        # ========================================================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarFrame") # [FIX] Đặt ID 
        self.sidebar.setFixedWidth(240)
        # [FIX] Khóa scope CSS chỉ áp dụng cho riêng SidebarFrame
        self.sidebar.setStyleSheet(f"#SidebarFrame {{ background-color: {Theme.SURFACE}; border-right: 1px solid {Theme.BORDER}; }}")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(6)

        logo_lbl = QLabel("✨ AI Subtitle Studio")
        logo_lbl.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; padding: 6px 4px 12px 4px; border: none;")
        sidebar_layout.addWidget(logo_lbl)

        sidebar_layout.addWidget(QLabel("NHẬP DỮ LIỆU", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 6px;"))
        sidebar_layout.addWidget(self.create_side_action_button("📂  Add Video...", self.select_videos))
        sidebar_layout.addWidget(self.create_side_action_button("📝  Add SRT / Draft...", self.select_srt_for_video))
        sidebar_layout.addWidget(self.create_side_action_button("✨  Edit Selected SRT", self.open_subtitle_editor))
        sidebar_layout.addWidget(self.create_side_action_button("🗑  Clear Queue", self.clear_files))

        sidebar_layout.addWidget(QLabel("WORKSPACE", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 10px;"))
        self.nav_btns = {}
        self.btn_nav_workspace = self.create_nav_button("🎬  Video Workspace", 0)
        sidebar_layout.addWidget(self.btn_nav_workspace)

        sidebar_layout.addWidget(QLabel("PIPELINE", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 10px;"))
        self.btn_nav_queue = self.create_nav_button("📋  Queue & Output", 1)
        sidebar_layout.addWidget(self.btn_nav_queue)

        sidebar_layout.addStretch()

        sidebar_layout.addWidget(QLabel("CẤU HÌNH", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none;"))
        self.btn_nav_settings = self.create_nav_button("⚙  AI & Settings", 2)
        sidebar_layout.addWidget(self.btn_nav_settings)

        root_layout.addWidget(self.sidebar)

        # ========================================================
        # 3. RIGHT AREA (TOPBAR + DASHBOARD + STACK + BOTTOMBAR)
        # ========================================================
        right_area = QWidget()
        right_area.setObjectName("RightArea")
        right_area.setStyleSheet(f"#RightArea {{ background-color: {Theme.BG_APP}; }}")
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # --- TOPBAR ---
        topbar = QFrame()
        topbar.setObjectName("TopbarFrame")
        topbar.setFixedHeight(46)
        topbar.setStyleSheet(f"#TopbarFrame {{ background-color: {Theme.BG_APP}; border-bottom: 1px solid {Theme.BORDER}; }}")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 0, 12, 0)

        self.lbl_page_title = QLabel("Video Workspace")
        self.lbl_page_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; border: none;")
        topbar_layout.addWidget(self.lbl_page_title)
        topbar_layout.addStretch()

        btn_minimize = QPushButton("—")
        btn_minimize.setFixedSize(28, 24)
        btn_minimize.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Theme.TEXT_SECONDARY}; border: none; border-radius: 4px; font-weight: bold; }}
            QPushButton:hover {{ background: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}
        """)
        btn_minimize.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 24)
        btn_close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Theme.DANGER}; border: none; border-radius: 4px; font-weight: bold; }}
            QPushButton:hover {{ background: {Theme.DANGER}; color: #FFFFFF; }}
        """)
        btn_close.clicked.connect(self.close)

        topbar_layout.addWidget(btn_minimize)
        topbar_layout.addWidget(btn_close)
        right_layout.addWidget(topbar)

        # --- DASHBOARD HARDWARE CARDS ---
        dash_frame = QFrame()
        dash_frame.setObjectName("DashFrame")
        dash_frame.setStyleSheet(f"#DashFrame {{ background-color: {Theme.SURFACE}; border-bottom: 1px solid {Theme.BORDER}; }}")
        dash_layout = QHBoxLayout(dash_frame)
        dash_layout.setContentsMargins(14, 6, 14, 6)
        dash_layout.setSpacing(8)

        self.lbl_gpu_val, card_gpu = self.create_metric_widget("GPU", "Detecting...", Theme.CYAN)
        self.lbl_vram_val, card_vram = self.create_metric_widget("VRAM", "-- / -- GB", Theme.PRIMARY_PURPLE)
        self.lbl_cpu_val, card_cpu = self.create_metric_widget("CPU", "0%", Theme.CYAN)
        self.lbl_lang_val, card_lang = self.create_metric_widget("Language", "Auto", Theme.TEXT_PRIMARY)
        self.lbl_queue_val, card_queue = self.create_metric_widget("Queue", "0 video", Theme.CYAN)
        self.lbl_status_val, card_status = self.create_metric_widget("Status", "Idle", Theme.SUCCESS)

        dash_layout.addWidget(card_gpu)
        dash_layout.addWidget(card_vram)
        dash_layout.addWidget(card_cpu)
        dash_layout.addWidget(card_lang)
        dash_layout.addWidget(card_queue)
        dash_layout.addWidget(card_status)
        right_layout.addWidget(dash_frame)

        # --- STACKED PAGES AREA ---
        self.stack = QStackedWidget()
        self.stack.setContentsMargins(12, 10, 12, 10)

        # PAGE 0: VIDEO WORKSPACE
        self.page_workspace = QWidget()
        workspace_layout = QVBoxLayout(self.page_workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(8)

        self.work_splitter = QSplitter(Qt.Vertical)
        self.work_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; height: 1px; margin: 1px 0px; }}")

        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(250)
        self.video_player.setContentsMargins(0, 0, 0, 8)
        self.work_splitter.addWidget(self.video_player)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Theme.BORDER}; border-radius: 4px; background: {Theme.SURFACE}; }}
            QTabBar::tab {{ background: {Theme.BG_APP}; color: {Theme.TEXT_MUTED}; padding: 6px 16px; border: 1px solid {Theme.BORDER}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {Theme.PRIMARY_PURPLE}; color: #FFFFFF; }}
            QTabBar::tab:hover:!selected {{ background: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}
        """)

        self.sub_editor = SubtitleEditorWidget()
        self.sub_editor.seek_requested.connect(self.video_player.set_position)
        self.video_player.sub_controller.subtitle_cleared.connect(self.sub_editor.clear_highlight)
        self.video_player.sub_controller.subtitle_changed.connect(
            lambda stt, start, text: self.sub_editor.highlight_row_by_stt(stt)
        )
        self.sub_editor.preview_toggled.connect(self.video_player.sub_controller.toggle_preview)
        self.sub_editor.style_changed.connect(
            lambda s: self.video_player.subtitle_overlay.update_style(
                family=s.get("family"),
                size=s.get("size"),
                color=s.get("color"),
                out_color=s.get("out_color"),
                out_width=s.get("out_width"),
                position=s.get("position")
            )
        )
        self.sub_editor.live_edit_applied.connect(self.video_player.sub_controller.update_live_data)
        self.sub_editor.fill_text_requested.connect(self.start_fill_text_worker)

        self.bottom_tabs.addTab(self.sub_editor, "📝 Subtitle Editor")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái hoạt động...")
        self.bottom_tabs.addTab(self.log_box, "📜 Live Log")

        self.work_splitter.addWidget(self.bottom_tabs)
        self.work_splitter.setStretchFactor(0, 1)
        self.work_splitter.setStretchFactor(1, 0)
        self.work_splitter.setSizes([430, 240])

        workspace_layout.addWidget(self.work_splitter)
        self.stack.addWidget(self.page_workspace)

        # PAGE 1: QUEUE & OUTPUT
        self.page_queue = QWidget()
        queue_page_layout = QVBoxLayout(self.page_queue)
        queue_page_layout.setContentsMargins(0, 0, 0, 0)
        queue_page_layout.setSpacing(10)

        self.queue_ui = QueueWidget()
        self.queue_ui.item_clicked.connect(self.on_queue_item_clicked)
        self.queue_ui.item_removed.connect(self.queue_mgr.remove_video)
        queue_page_layout.addWidget(self.queue_ui, stretch=1)
        self.stack.addWidget(self.page_queue)

        # PAGE 2: AI & SETTINGS
        self.page_settings = QWidget()
        settings_page_layout = QVBoxLayout(self.page_settings)
        settings_page_layout.setContentsMargins(10, 10, 10, 10)
        settings_page_layout.setSpacing(12)

        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        settings_content = QWidget()
        settings_form = QVBoxLayout(settings_content)
        settings_form.setSpacing(10)

        # Settings Card 1
        ai_card = QFrame()
        ai_card.setObjectName("SettingsCard")
        ai_card.setStyleSheet(f"#SettingsCard {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 10px; }}")
        ai_card_layout = QVBoxLayout(ai_card)
        ai_card_layout.setSpacing(8)

        ai_card_title = QLabel("🤖 Cấu hình Whisper Engine")
        ai_card_title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {Theme.CYAN}; border: none;")
        ai_card_layout.addWidget(ai_card_title)

        ai_grid = QGridLayout()
        ai_grid.setSpacing(8)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Full Subtitle (AI sinh Text)", "full")
        self.mode_combo.addItem("Timing Draft (Chỉ tạo khung thời gian)", "timing")
        self.mode_combo.currentIndexChanged.connect(
            lambda: self.chk_hardsub.setEnabled(self.mode_combo.currentData() == "full")
        )
        ai_grid.addWidget(QLabel("Chế độ xử lý (Pipeline Mode):"), 0, 0)
        ai_grid.addWidget(self.mode_combo, 0, 1)

        self.model_combo = QComboBox()
        self.model_combo.addItem("Large V3 Turbo (Khuyên dùng - Nhanh)", "large-v3-turbo")
        self.model_combo.addItem("Large V3 (Chuẩn gốc)", "large-v3")
        ai_grid.addWidget(QLabel("Whisper Model Size:"), 1, 0)
        ai_grid.addWidget(self.model_combo, 1, 1)

        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Float16 (RTX GPU)", "float16")
        self.compute_combo.addItem("Int8_Float16 (Save VRAM)", "int8_float16")
        ai_grid.addWidget(QLabel("Kiểu tính toán (VRAM):"), 2, 0)
        ai_grid.addWidget(self.compute_combo, 2, 1)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Context / Thuật ngữ chuyên ngành...")
        ai_grid.addWidget(QLabel("Initial Prompt:"), 3, 0)
        ai_grid.addWidget(self.prompt_input, 3, 1)

        vad_box = QHBoxLayout()
        self.chk_vad = QCheckBox("Bật VAD Filter")
        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(100, 2000)
        self.spin_silence.setValue(500)
        self.spin_silence.setEnabled(False)
        self.chk_vad.toggled.connect(lambda c: self.spin_silence.setEnabled(c))
        vad_box.addWidget(self.chk_vad)
        vad_box.addWidget(QLabel("Silence (ms):"))
        vad_box.addWidget(self.spin_silence)
        ai_grid.addWidget(QLabel("Lọc khoảng lặng:"), 4, 0)
        ai_grid.addLayout(vad_box, 4, 1)

        ai_card_layout.addLayout(ai_grid)
        settings_form.addWidget(ai_card)

        # Settings Card 2
        hardsub_card = QFrame()
        hardsub_card.setObjectName("SettingsCard")
        hardsub_card.setStyleSheet(f"#SettingsCard {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 10px; }}")
        hardsub_card_layout = QVBoxLayout(hardsub_card)
        hardsub_card_layout.setSpacing(8)

        hardsub_card_title = QLabel("🎬 Cấu hình Hardsub FFmpeg")
        hardsub_card_title.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {Theme.CYAN}; border: none;")
        hardsub_card_layout.addWidget(hardsub_card_title)

        hardsub_grid = QGridLayout()
        hardsub_grid.setSpacing(8)

        self.chk_hardsub = QCheckBox("Chèn Hardsub tự động vào Video")
        self.chk_hardsub.setChecked(True)
        hardsub_grid.addWidget(self.chk_hardsub, 0, 0, 1, 2)

        self.font_combo = QComboBox()
        font = self.font_combo.font()
        font.setPointSize(10)
        self.font_combo.setFont(font)
        for f in ["Noto Sans JP", "Arial", "Segoe UI"]:
            self.font_combo.addItem(f, f)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(42)

        font_box = QHBoxLayout()
        font_box.addWidget(self.font_combo, stretch=2)
        font_box.addWidget(QLabel("Cỡ chữ:"))
        font_box.addWidget(self.size_spin, stretch=1)

        hardsub_grid.addWidget(QLabel("Font chữ mặc định:"), 1, 0)
        hardsub_grid.addLayout(font_box, 1, 1)

        hardsub_card_layout.addLayout(hardsub_grid)
        settings_form.addWidget(hardsub_card)
        settings_form.addStretch()

        settings_scroll.setWidget(settings_content)
        settings_page_layout.addWidget(settings_scroll)
        self.stack.addWidget(self.page_settings)

        right_layout.addWidget(self.stack, stretch=1)

        # =========================================================
        # 4. GLOBAL BOTTOM CONTROL BAR (PROGRESS & ACTIONS)
        # =========================================================
        bottom_frame = QFrame()
        bottom_frame.setObjectName("BottomFrame")
        bottom_frame.setStyleSheet(f"#BottomFrame {{ background-color: {Theme.SURFACE}; border-top: 1px solid {Theme.BORDER}; }}")
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(14, 8, 14, 10)
        bottom_layout.setSpacing(6)

        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        lbl_out = QLabel("📁 Output:")
        lbl_out.setStyleSheet(f"font-weight: bold; color: {Theme.TEXT_MUTED}; font-size: 11px;")
        self.out_input = QLineEdit()
        self.out_input.setPlaceholderText("Thư mục lưu kết quả xuất video mặc định...")
        out_btn = QPushButton("Browse...")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self.select_output_dir)

        output_row.addWidget(lbl_out)
        output_row.addWidget(self.out_input, stretch=1)
        output_row.addWidget(out_btn)
        bottom_layout.addLayout(output_row)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Theme.BG_APP};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                text-align: center;
                color: {Theme.TEXT_PRIMARY};
                height: 14px;
            }}
            QProgressBar::chunk {{
                background: {Theme.PRIMARY_GRADIENT};
                border-radius: 3px;
            }}
        """)
        self.progress_anim = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_anim.setDuration(400)

        self.lbl_speed_eta = QLabel("Speed: 0.0x  |  ETA: --")
        self.lbl_speed_eta.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold; font-size: 11px;")

        prog_row.addWidget(self.progress_bar, stretch=4)
        prog_row.addWidget(self.lbl_speed_eta, stretch=1)
        bottom_layout.addLayout(prog_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.start_btn = QPushButton("▶ Start Queue")
        self.start_btn.setObjectName("btn_primary")
        self.start_btn.clicked.connect(self.start_processing)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("btn_danger")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setObjectName("btn_secondary")
        open_folder_btn.clicked.connect(self.open_output_folder)

        action_row.addWidget(self.start_btn, stretch=3)
        action_row.addWidget(self.cancel_btn, stretch=1)
        action_row.addWidget(open_folder_btn, stretch=1)
        bottom_layout.addLayout(action_row)

        right_layout.addWidget(bottom_frame)
        root_layout.addWidget(right_area)

        # =========================================================
        # 5. POST INITIALIZATION
        # =========================================================
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

    # =========================================================
    # NAVIGATION HELPERS
    # =========================================================
    def create_nav_button(self, text, page_index, disabled=False):
        btn = QPushButton(text)
        btn.setFixedHeight(34)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Theme.TEXT_SECONDARY};
                text-align: left;
                padding-left: 10px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.TEXT_PRIMARY};
            }}
            QPushButton:disabled {{
                color: {Theme.TEXT_DISABLED};
            }}
        """)
        if disabled:
            btn.setEnabled(False)
        else:
            btn.clicked.connect(lambda: self.switch_page(page_index))
        self.nav_btns[page_index] = btn
        return btn

    def create_side_action_button(self, text, slot):
        btn = QPushButton(text)
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE_ELEVATED};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                color: {Theme.TEXT_PRIMARY};
                text-align: left;
                padding-left: 10px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border: 1px solid {Theme.CYAN};
                color: {Theme.CYAN};
                background-color: {Theme.SURFACE_SOFT};
            }}
        """)
        btn.clicked.connect(slot)
        return btn

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for idx, btn in self.nav_btns.items():
            if idx == index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {Theme.SURFACE_SOFT};
                        color: {Theme.PRIMARY_PURPLE};
                        text-align: left;
                        padding-left: 10px;
                        border-radius: 6px;
                        font-weight: bold;
                        font-size: 12px;
                        border: 1px solid {Theme.BORDER};
                    }}
                """)
                clean_title = btn.text().replace('🎬', '').replace('📋', '').replace('⚙', '').strip()
                self.lbl_page_title.setText(clean_title)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {Theme.TEXT_SECONDARY};
                        text-align: left;
                        padding-left: 10px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: {Theme.SURFACE_SOFT};
                        color: {Theme.TEXT_PRIMARY};
                    }}
                """)

    # --- KHẮC PHỤC SCOPE CHO HÀM TẠO METRIC CARD ---
    def create_metric_widget(self, title, value, color):
        frame = QFrame()
        frame.setObjectName("MetricCard")
        frame.setStyleSheet(f"#MetricCard {{ background: {Theme.BG_APP}; border: 1px solid {Theme.BORDER}; border-radius: 5px; padding: 2px 8px; }}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none;")
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; border: none;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return lbl_val, frame

    # =========================================================
    # EVENT HANDLERS & LOGIC PRESERVATION (SPRINT 5 CORE)
    # =========================================================
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')

        added_files = []
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.lower().endswith(valid_extensions):
                if self.queue_mgr.add_video(file_path):
                    added_files.append(file_path)

        if added_files:
            self._start_metadata_worker(added_files)
            self.on_queue_item_clicked(added_files[-1])

    def apply_saved_settings(self):
        settings = load_settings()
        if not settings:
            return

        if "mode" in settings:
            idx = self.mode_combo.findData(settings["mode"])
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)

        if "model_size" in settings:
            idx = self.model_combo.findData(settings["model_size"])
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

        if "compute_type" in settings:
            idx = self.compute_combo.findData(settings["compute_type"])
            if idx >= 0:
                self.compute_combo.setCurrentIndex(idx)

        if "prompt" in settings:
            self.prompt_input.setText(settings["prompt"])
        if "font_name" in settings:
            self.font_combo.setCurrentText(settings["font_name"])
        if "font_size" in settings:
            self.size_spin.setValue(settings["font_size"])
        if "do_hardsub" in settings:
            self.chk_hardsub.setChecked(settings["do_hardsub"])

        if "use_vad" in settings:
            self.chk_vad.setChecked(settings["use_vad"])
        if "silence_ms" in settings:
            self.spin_silence.setValue(settings["silence_ms"])

        if "output_dir" in settings:
            self.out_input.setText(settings["output_dir"])

    def update_hardware_info(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.lbl_gpu_val.setText(torch.cuda.get_device_name(0))
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                alloc = torch.cuda.memory_allocated(0) / (1024**3)
                self.lbl_vram_val.setText(f"{alloc:.1f} / {total:.1f} GB")
            else:
                self.lbl_gpu_val.setText("CPU Only")
                self.lbl_vram_val.setText("N/A")
        except Exception:
            self.lbl_gpu_val.setText("RTX GPU")

    def update_cpu_usage(self):
        try:
            import psutil
            self.lbl_cpu_val.setText(f"{psutil.cpu_percent(interval=None):.1f}%")
        except Exception:
            pass

    def _start_metadata_worker(self, video_paths):
        if not video_paths:
            return

        if not hasattr(self, 'meta_workers'):
            self.meta_workers = []

        worker = MetadataWorker(video_paths)
        worker.metadata_parsed.connect(self.queue_mgr.update_metadata)
        worker.finished.connect(lambda w=worker: self.meta_workers.remove(w) if w in self.meta_workers else None)

        self.meta_workers.append(worker)
        worker.start()

    def select_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if files:
            added_files = []
            for f in files:
                if self.queue_mgr.add_video(f):
                    added_files.append(f)

            self._start_metadata_worker(added_files)
            if added_files:
                self.on_queue_item_clicked(added_files[-1])

    def select_srt_for_video(self):
        video_path, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if video_path:
            srt_path, _ = QFileDialog.getOpenFileName(self, "Chọn file Phụ đề / Draft", "", "Subtitle & Draft (*.srt *.ai-subtitle-draft)")
            if srt_path:
                if video_path not in self.queue_mgr.get_items():
                    self.queue_mgr.add_video(video_path)
                    self._start_metadata_worker([video_path])

                self.queue_mgr.set_srt_for_video(video_path, srt_path)
                self.on_queue_item_clicked(video_path)

    def clear_files(self):
        self.queue_mgr.clear_queue()

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục đầu ra")
        if d:
            self.out_input.setText(d)

    def on_queue_updated(self):
        items = self.queue_mgr.get_items()
        self.queue_ui.sync_with_manager(items, self.queue_mgr.active_vid)

        count = len(items)
        self.lbl_queue_val.setText(f"{count} video" if count <= 1 else f"{count} videos")

        if count == 0:
            if hasattr(self, 'video_player'):
                self.video_player.cleanup()
                self.video_player.sub_controller.load_srt(None)
            if hasattr(self, 'sub_editor'):
                self.sub_editor.all_segments.clear()
                self.sub_editor.render_page()

    def start_processing(self):
        items = self.queue_mgr.get_items()
        if not items:
            return

        self.is_cancelled_flag = False
        self.batch_queue = [(vid, data.get("srt_path")) for vid, data in items.items()]
        self.total_batch_items = len(self.batch_queue)
        self.current_batch_index = 0
        self.output_dir = self.out_input.text().strip()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_box.clear()

        self.lbl_status_val.setText("Processing")
        self.lbl_status_val.setStyleSheet(f"color: {Theme.WARNING}; font-size: 11px; font-weight: bold; border: none;")

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
        self.append_log(f"🎬 ĐANG XỬ LÝ VIDEO [{self.current_batch_index}/{self.total_batch_items}]: {file_name}")
        self.append_log(f"==================================================")

        self.on_queue_item_clicked(self.current_vid)

        if not current_srt:
            self.append_log("[HỆ THỐNG] Khởi tạo luồng AI Whisper...")
            self.worker = WhisperWorker(
                video_path=self.current_vid,
                output_dir=self.output_dir,
                initial_prompt=self.prompt_input.text().strip(),
                compute_type=self.compute_combo.currentData(),
                use_vad=self.chk_vad.isChecked(),
                min_silence_ms=self.spin_silence.value(),
                model_size=self.model_combo.currentData(),
                generation_mode=self.mode_combo.currentData()
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_whisper_finished)
            self.worker.error_signal.connect(self.process_error)
            self.worker.start()
        else:
            self.append_log(f"[HỆ THỐNG] Phát hiện file đính kèm: {current_srt}")

            if current_srt.endswith('.ai-subtitle-draft'):
                self.append_log("❌ [TỪ CHỐI] Không thể chèn Hardsub trực tiếp từ file Draft JSON.")
                self.append_log("💡 Hướng dẫn: Mở Draft trên Editor ➜ Điền chữ AI ➜ [Lưu SRT] ➜ Đưa file SRT vào Queue để Hardsub.")
                self.process_next_batch_item()
                return

            if self.chk_hardsub.isChecked():
                self.append_log("[HỆ THỐNG] Bỏ qua xác nhận. Khởi chạy luồng Hardsub (FFmpeg) ngay lập tức...")
                self.worker = HardsubWorker(
                    video_path=self.current_vid,
                    srt_path=current_srt,
                    output_dir=self.output_dir,
                    font_size=self.size_spin.value(),
                    font_color="white",
                    font_name=self.font_combo.currentText()
                )
                self.worker.progress_signal.connect(self.update_progress)
                self.worker.log_signal.connect(self.append_log)
                self.worker.finished_signal.connect(self.on_hardsub_finished)
                self.worker.error_signal.connect(self.process_error)
                self.worker.start()
            else:
                self.log_skip_hardsub()
                self.process_next_batch_item()

    def on_whisper_finished(self, msg, srt_path):
        self.append_log(f"[AI] {msg}")
        self.queue_mgr.set_srt_for_video(self.current_vid, srt_path)

        if self.mode_combo.currentData() == "timing":
            self.append_log("[HỆ THỐNG] Đã tạo xong Timing Artifact. Chuyển sang Subtitle Editor để kiểm duyệt...")
            self.switch_page(0)
            self.on_queue_item_clicked(self.current_vid)
            self.bottom_tabs.setCurrentIndex(0)
            self.process_finished("Đã tạo xong khung thời gian (Timing Draft)! Vui lòng kiểm duyệt trên Editor.")
            return

        if self.chk_hardsub.isChecked():
            self.show_confirm_dialog(self.current_vid, srt_path)
        else:
            self.log_skip_hardsub()
            self.process_next_batch_item()

    def log_skip_hardsub(self):
        if hasattr(self, 'batch_queue') and len(self.batch_queue) > 0:
            self.append_log("[HỆ THỐNG] Bỏ qua Hardsub (theo Cài đặt). Chuyển sang Video tiếp theo...")
        else:
            self.append_log("[HỆ THỐNG] Bỏ qua Hardsub (theo Cài đặt). Đã xử lý xong video cuối cùng.")

    def show_confirm_dialog(self, vid_path, srt_path):
        self.progress_bar.setValue(100)
        self.lbl_speed_eta.setText("Chờ xác nhận từ người dùng...")

        from ui.hardsub_confirm_dialog import HardsubConfirmDialog
        dialog = HardsubConfirmDialog(vid_path, self)
        dialog.exec()

        choice = dialog.user_choice
        if choice == HardsubConfirmDialog.HARDSUB:
            self.append_log("[HỆ THỐNG] Chấp thuận. Khởi chạy luồng Hardsub (FFmpeg)...")
            self.worker = HardsubWorker(
                video_path=vid_path,
                srt_path=srt_path,
                output_dir=self.output_dir,
                font_size=self.size_spin.value(),
                font_color="white",
                font_name=self.font_combo.currentText()
            )
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.log_signal.connect(self.append_log)
            self.worker.finished_signal.connect(self.on_hardsub_finished)
            self.worker.error_signal.connect(self.process_error)
            self.worker.start()

        elif choice == HardsubConfirmDialog.EDIT:
            self.append_log("[HỆ THỐNG] User chọn Edit. Tạm dừng tiến trình Batch để chỉnh sửa.")
            self.switch_page(0)
            self.bottom_tabs.setCurrentIndex(0)
            self.on_queue_item_clicked(vid_path)

            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.lbl_status_val.setText("Idle")
            self.lbl_status_val.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 11px; font-weight: bold; border: none;")
            self.progress_anim.stop()
            self.progress_bar.setValue(0)
            self.lbl_speed_eta.setText("Tiến trình tạm dừng để chỉnh sửa.")

        else:
            if hasattr(self, 'batch_queue') and len(self.batch_queue) > 0:
                self.append_log("[HỆ THỐNG] User chọn Bỏ qua. SRT đã được bảo toàn. Next Video...")
            else:
                self.append_log("[HỆ THỐNG] User chọn Bỏ qua. SRT đã được bảo toàn. Đã xử lý xong.")
            self.process_next_batch_item()

    def on_hardsub_finished(self, msg, out_video_path):
        self.append_log(f"[FFmpeg] Xuất file thành công: {out_video_path}")
        self.process_next_batch_item()

    def cancel_processing(self):
        self.is_cancelled_flag = True
        self.batch_queue = []
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("[HỆ THỐNG] Đang hủy tiến trình an toàn...")
            self.cancel_btn.setEnabled(False)

    def update_progress(self, val, msg):
        if hasattr(self, 'total_batch_items') and self.total_batch_items > 0:
            base_p = ((self.current_batch_index - 1) / self.total_batch_items) * 100
            file_p = (val / self.total_batch_items)
            global_val = int(base_p + file_p)
        else:
            global_val = val

        self.progress_anim.stop()
        self.progress_anim.setStartValue(self.progress_bar.value())
        self.progress_anim.setEndValue(global_val)
        self.progress_anim.start()

        if msg and "Chờ xác nhận" not in self.lbl_speed_eta.text():
            self.lbl_speed_eta.setText(msg)

    def append_log(self, msg):
        self.log_box.append(msg)
        speed_match = re.search(r"speed=\s*([0-9\.]+x)", msg)
        if speed_match:
            self.lbl_speed_eta.setText(f"Speed: {speed_match.group(1)}")

    def process_finished(self, msg):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if hasattr(self, 'sub_editor'):
            if hasattr(self.sub_editor, 'fill_text_btn'):
                self.sub_editor.fill_text_btn.setEnabled(True)
            if hasattr(self.sub_editor, 'save_btn'):
                self.sub_editor.save_btn.setEnabled(True)

        self.lbl_status_val.setText("Idle")
        self.lbl_status_val.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 11px; font-weight: bold; border: none;")
        self.progress_anim.stop()
        self.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("Speed: 0.0x  |  ETA: --")

        Toast.show_success(self, msg)

    def process_error(self, err):
        self.append_log(f"❌ [LỖI] {err}")
        if getattr(self, 'is_cancelled_flag', False) or "hủy" in str(err).lower():
            self.process_finished("Tiến trình đã bị dừng.")
        elif hasattr(self, 'batch_queue') and len(self.batch_queue) > 0:
            self.append_log("[HỆ THỐNG] Bỏ qua video lỗi, tiếp tục với video tiếp theo trong Queue...")
            self.process_next_batch_item()
        else:
            self.process_finished("Tiến trình hoàn tất (có phát sinh lỗi ở file cuối).")

    def open_subtitle_editor(self):
        if not self.queue_mgr.get_items():
            return

        vid, srt = self.queue_mgr.get_active_data()
        if not vid:
            vid = list(self.queue_mgr.get_items().keys())[0]
            srt = self.queue_mgr.get_items()[vid].get("srt_path")

        if not srt or not os.path.exists(srt):
            base = os.path.splitext(vid)[0]
            srt = f"{base}.srt"
            if not os.path.exists(srt):
                with open(srt, "w", encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 00:00:05,000\n[AI Subtitle Studio Placeholder]\n")
            self.queue_mgr.set_srt_for_video(vid, srt)

        self.switch_page(0)
        self.on_queue_item_clicked(vid)

    def open_output_folder(self):
        out_d = self.out_input.text().strip()
        items = self.queue_mgr.get_items()
        if not out_d and items:
            out_d = os.path.dirname(list(items.keys())[0])

        if out_d and os.path.exists(out_d):
            os.startfile(out_d)

    def closeEvent(self, event):
        settings = {
            "mode": self.mode_combo.currentData(),
            "model_size": self.model_combo.currentData(),
            "compute_type": self.compute_combo.currentData(),
            "prompt": self.prompt_input.text().strip(),
            "use_vad": self.chk_vad.isChecked(),
            "silence_ms": self.spin_silence.value(),
            "do_hardsub": self.chk_hardsub.isChecked(),
            "font_name": self.font_combo.currentText(),
            "font_size": self.size_spin.value(),
            "output_dir": self.out_input.text().strip()
        }
        save_settings(settings)

        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)

        try:
            if os.name == 'nt':
                subprocess.Popen(
                    ["taskkill", "/f", "/im", "ffmpeg.exe"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
        except Exception:
            pass
        event.accept()

    def on_queue_item_clicked(self, vid_path):
        self.queue_mgr.set_active(vid_path)
        _, srt_path = self.queue_mgr.get_active_data()

        self.video_player.load_video(vid_path)

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

        self.bottom_tabs.setCurrentIndex(0)

    def on_queue_item_removed_handler(self, vid_path):
        items = self.queue_mgr.get_items()
        if not items:
            try:
                self.video_player.player.stop()
                self.video_player.player.setSource(QUrl())
            except Exception:
                pass

            self.video_player.cleanup()
            self.video_player.sub_controller.load_srt(None)
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
        else:
            if self.queue_mgr.active_vid:
                self.on_queue_item_clicked(self.queue_mgr.active_vid)

    # =========================================================================
    # ĐIỀU PHỐI LUỒNG FILL TEXT WORKER (P2-T13, P2-T14)
    # =========================================================================
    def start_fill_text_worker(self, start_idx, count):
        if not self.queue_mgr.active_vid:
            Toast.show_info(self, "Vui lòng chọn video từ Hàng đợi để điền chữ.")
            return

        target_segments = self.sub_editor.all_segments[start_idx : start_idx + count]

        segments_for_ai = []
        for seg in target_segments:
            s_ms = self.sub_editor.time_str_to_ms(seg['start'])
            e_ms = self.sub_editor.time_str_to_ms(seg['end'])
            raw_text = seg['text'] if seg['text'] != "[ Chưa có nội dung ]" else ""
            stt = int(seg['stt']) if str(seg['stt']).isdigit() else 0
            segments_for_ai.append((s_ms, e_ms, raw_text, stt))

        if not segments_for_ai:
            return

        self.is_cancelled_flag = False
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.sub_editor.btn_continue.setEnabled(False)
        self.sub_editor.save_draft_btn.setEnabled(False)
        self.sub_editor.save_btn.setEnabled(False)

        self.switch_page(0)
        self.bottom_tabs.setCurrentIndex(1)
        self.append_log(f"\n[HỆ THỐNG] Đang chạy AI Điền chữ cho {len(segments_for_ai)} câu (Từ dòng {start_idx + 1})...")

        self.worker = FillTextWorker(
            video_path=self.queue_mgr.active_vid,
            segments_data=segments_for_ai,
            initial_prompt=self.prompt_input.text().strip(),
            compute_type=self.compute_combo.currentData(),
            model_size=self.model_combo.currentData()
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_fill_text_finished)
        self.worker.error_signal.connect(self.process_error)
        self.worker.start()

    def on_fill_text_finished(self, filled_segments):
        self.switch_page(0)
        self.bottom_tabs.setCurrentIndex(0)

        for start_ms, end_ms, text, stt in filled_segments:
            for seg in self.sub_editor.all_segments:
                if str(seg['stt']) == str(stt):
                    seg['text'] = text
                    seg['status'] = 'draft'
                    break

        self.sub_editor.render_page()
        self.sub_editor.update_draft_progress()

        self.sub_editor.save_draft(silent=True)
        self.append_log("[HỆ THỐNG] Đã lưu Checkpoint Draft ngầm.")

        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_anim.stop()
        self.progress_bar.setValue(100)
        self.lbl_speed_eta.setText("Batch AI hoàn tất! Sẵn sàng cho lượt tiếp theo.")
        self.sub_editor.save_draft_btn.setEnabled(True)
        self.sub_editor.save_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())