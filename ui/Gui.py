import os
import re
import subprocess
import sys

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
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
from PySide6.QtCore import QObject, Signal


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
    def __init__(self):
        super().__init__()
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

        sidebar_layout.addWidget(QLabel("NHẬP LIỆU", styleSheet=f"color: {Theme.TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none; padding-top: 4px;"))
        sidebar_layout.addWidget(self.create_side_action_button("📂  Add Video...", self.select_videos))
        sidebar_layout.addWidget(self.create_side_action_button("📝  Add SRT / Draft...", self.select_srt_for_video))
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

        root_layout.addWidget(self.sidebar)

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
        self.stack = QStackedWidget()

        # Page 0: Dashboard
        self.page_dashboard = DashboardPage()
        self.page_dashboard.navigate_requested.connect(self.switch_page)
        self.stack.addWidget(self.page_dashboard)

        # Page 1: Video Workspace (Chứa luôn Subtitle Editor, không tách riêng)
        self.page_workspace = QWidget()
        ws_layout = QVBoxLayout(self.page_workspace)
        ws_layout.setContentsMargins(8, 8, 8, 8)
        ws_layout.setSpacing(6)

        self.work_splitter = QSplitter(Qt.Vertical)
        self.work_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Theme.BORDER}; height: 1px; margin: 1px 0px; }}")

        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(200)
        self.work_splitter.addWidget(self.video_player)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Theme.BORDER}; border-radius: 4px; background: {Theme.SURFACE}; }}
            QTabBar::tab {{ background: {Theme.BG_APP}; color: {Theme.TEXT_MUTED}; padding: 6px 16px; border: 1px solid {Theme.BORDER}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {Theme.PRIMARY_PURPLE}; color: #FFFFFF; }}
        """)

        # Khởi tạo Subtitle Editor ĐỘC NHẤT tại đây
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
        
        self.bottom_tabs.addTab(self.sub_editor, "📝 Inline Editor")

        self.ai_panel = AIGenerationPanel()
        self.ai_panel.start_requested.connect(self.start_processing)
        self.ai_panel.cancel_requested.connect(self.cancel_processing)
        self.bottom_tabs.addTab(self.ai_panel, "🤖 AI Generation")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái...")
        self.bottom_tabs.addTab(self.log_box, "📜 Live Log")

        self.work_splitter.addWidget(self.bottom_tabs)
        self.work_splitter.setSizes([380, 240])
        ws_layout.addWidget(self.work_splitter)
        
        # Đăng ký Page 1 vào Stack (Index 1)
        self.stack.addWidget(self.page_workspace)

        # [S6-FIX] Bỏ hoàn toàn Page 2 (Standalone Subtitle Editor) để tránh lỗi duplicate Widget

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

        # [CHÈN VỊ TRÍ 1 TẠI ĐÂY]
        # 1. Đồng bộ 2 chiều Batch Size giữa Inline Editor và AI Panel
        self.ai_panel.batch_spin.valueChanged.connect(self.sub_editor.spin_batch.setValue)
        self.sub_editor.spin_batch.valueChanged.connect(self.ai_panel.batch_spin.setValue)

        # 2. Nối action Continue từ Draft Center
        self.page_drafts.continue_draft_requested.connect(self._continue_draft_from_center)

        self.stack.addWidget(self.page_drafts)

        # Page 5 (Index 4): Export Center
        self.page_export = ExportCenterPage()
        # [FIX] Nối nút xuất file tới hàm xử lý đa định dạng thay vì chỉ lưu SRT của Editor
        self.page_export.export_srt_requested.connect(self._trigger_export_softsub)
        
        # [FIX MEDIUM #4] Kích hoạt nút Retry
        self.ai_panel.retry_requested.connect(self._retry_current_task)
        self.page_export.burn_hardsub_requested.connect(self._trigger_export_hardsub)
        self.stack.addWidget(self.page_export)

        # Page 6 (Index 5): Settings Center
        self.page_settings = SettingsCenterPage()
        self.stack.addWidget(self.page_settings)

        right_layout.addWidget(self.stack, stretch=1)

        # ========================================================
        # 4. COMPACT GLOBAL BOTTOM BAR (Chống ép dẹp - High DPI Safe)
        # ========================================================
        bottom_frame = QFrame()
        bottom_frame.setObjectName("BottomFrame")
        # [S6-FIX] Dùng min-height để tự nở rộng nếu màn hình DPI lớn
        bottom_frame.setMinimumHeight(96)
        bottom_frame.setStyleSheet(f"#BottomFrame {{ background-color: {Theme.SURFACE}; border-top: 1px solid {Theme.BORDER}; }}")
        bottom_layout = QVBoxLayout(bottom_frame)
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
        right_layout.addWidget(bottom_frame)
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
        # [S6-FIX ROUTING] Vì đã xóa Page 2 (Subtitle Editor view rỗng)
        # Nếu bấm nút số 2 -> Trả về Workspace (Index 1) và bật tab Subtitle.
        # Các nút từ 3 trở đi sẽ bị trừ đi 1 index để match với Stack.
        
        target_stack_idx = original_index
        if original_index == 2:
            target_stack_idx = 1
        elif original_index > 2:
            target_stack_idx = original_index - 1

        self.stack.setCurrentIndex(target_stack_idx)
        
        if original_index == 2:
            self.bottom_tabs.setCurrentIndex(0) # Mở Tab Editor
            
        for idx, btn in self.nav_btns.items():
            if idx == original_index:
                btn.setStyleSheet(f"QPushButton {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.PRIMARY_PURPLE}; text-align: left; padding-left: 10px; border-radius: 6px; font-weight: bold; font-size: 12px; border: 1px solid {Theme.BORDER}; }}")
                clean_title = re.sub(r"[^\w\s]", "", btn.text()).strip()
                self.lbl_page_title.setText(clean_title)
            else:
                btn.setStyleSheet(f"QPushButton {{ background-color: transparent; color: {Theme.TEXT_SECONDARY}; text-align: left; padding-left: 10px; border-radius: 6px; font-weight: 600; font-size: 12px; border: none; }} QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; color: {Theme.TEXT_PRIMARY}; }}")

        if original_index == 4:
            self.page_drafts.set_directory(self.out_input.text().strip() or (os.path.dirname(list(self.queue_mgr.get_items().keys())[0]) if self.queue_mgr.get_items() else ""))

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
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            # [FIX] Đảm bảo controller xả rỗng dữ liệu cũ
            self.video_player.sub_controller.load_srt(None)

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

    def on_queue_item_removed_handler(self, vid_path):
        items = self.queue_mgr.get_items()
        if not items:
            self.video_player.cleanup()
            self.sub_editor.all_segments.clear()
            self.sub_editor.render_page()
            # [FIX] Đảm bảo controller xả rỗng dữ liệu cũ
            self.video_player.sub_controller.load_srt(None)
        elif self.queue_mgr.active_vid:
            self.on_queue_item_clicked(self.queue_mgr.active_vid)

    def _load_draft_from_center(self, draft_path, silent=False):
        """Nạp chính xác file Draft vào Workspace và QueueManager mà không làm mất text."""
        if not draft_path or not os.path.exists(draft_path):
            Toast.show_error(self, "Tập tin Draft không tồn tại.")
            return False

        # 1. Trích xuất tên video gốc từ tên file draft
        draft_filename = os.path.basename(draft_path)
        base_key = draft_filename.replace(".ai-subtitle-draft", "").replace("_timing", "")
        
        # 2. Tìm video trong Queue khớp với key
        target_vid = None
        for vid in self.queue_mgr.get_items().keys():
            vid_name = os.path.splitext(os.path.basename(vid))[0]
            if vid_name == base_key or vid_name.startswith(base_key) or base_key.startswith(vid_name):
                target_vid = vid
                break

        if not target_vid:
            Toast.show_error(self, "Vui lòng nạp video gốc tương ứng vào Queue trước khi mở Draft.")
            return False

        # 3. Gán file draft này làm phụ đề chính thức của video trong QueueManager
        self.queue_mgr.set_active(target_vid)
        self.queue_mgr.set_srt_for_video(target_vid, draft_path)

        # 4. Load video vào Player và nạp TRỰC TIẾP file draft vào SubEditor
        self.video_player.load_video(target_vid)
        self.sub_editor.load_draft_file(draft_path)
        self.video_player.sub_controller.load_srt(draft_path)

        # 5. Chuyển sang Workspace
        self.switch_page(1)
        self.bottom_tabs.setCurrentIndex(0)
        
        # [FIX] Chỉ hiện Toast khi người dùng bấm 'Mở Editor', không hiện khi chạy qua nút 'Continue'
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
            
        # Khóa UI an toàn, chống crash do click nhiều lần đè luồng đang chạy
        if hasattr(self, 'worker') and self.worker.isRunning():
            Toast.show_info(self, "Hệ thống đang bận xử lý, vui lòng chờ...")
            return
            
        out_dir = self.page_export.out_edit.text().strip() or self.out_input.text().strip()
        
        # Bật cờ hệ thống sang trạng thái Processing
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
        
        # [FIX CRITICAL] Chuyển signal connect sang method của class để tránh bị Garbage Collector thu hồi
        self.worker.finished_signal.connect(self._on_manual_hardsub_success)
        self.worker.error_signal.connect(self._on_manual_hardsub_error)
        self.worker.start()

        # --- BỔ SUNG 2 HÀM XỬ LÝ MỚI ---
    def _on_manual_hardsub_success(self, msg, path):
        Toast.show_success(self, f"Render Hardsub xong: {path}")
        # Đưa thanh tiến độ về 100% (màu hồng hoàn tất)
        self.progress_bar.setValue(100)
        self.page_dashboard.quick_progress.setValue(100)
        # Kích hoạt bộ đếm thời gian: Đợi 2.5 giây sau đó tự động reset UI về 0 (Idle)
        QTimer.singleShot(2500, self._cleanup_ui_after_task)

    def _on_manual_hardsub_error(self, err):
        Toast.show_error(self, f"Lỗi Hardsub: {err}")
        self._cleanup_ui_after_task()
        
        # [FIX] Đảm bảo dọn dẹp sạch sẽ thanh Progress UI khi hoàn tất hoặc gặp lỗi
        def on_success(msg, path):
            Toast.show_success(self, f"Render Hardsub xong: {path}")
            self._cleanup_ui_after_task()
            
        def on_error(err):
            Toast.show_error(self, f"Lỗi Hardsub: {err}")
            self._cleanup_ui_after_task()
            
        self.worker.finished_signal.connect(on_success)
        self.worker.error_signal.connect(on_error)
        self.worker.start()

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
            # [FIX] Thêm Log thông báo cho người dùng biết hệ thống đang làm gì
            if self.ai_panel.mode_combo.currentData() == "timing":
                self.append_log("[AI] Bắt đầu chế độ Timing Only (Chỉ trích xuất thời gian).")
                self.append_log("[AI] Đang chạy thuật toán VAD (Silero) để phân tách giọng nói...")
                self.append_log("[AI] Quá trình này chạy ngầm và rất nhanh, vui lòng đợi...")
            self.worker = WhisperWorker(
                video_path=self.current_vid,
                output_dir=self.output_dir,
                initial_prompt=self.ai_panel.prompt_edit.text().strip(),
                compute_type=self.page_settings.compute_combo.currentData(),
                use_vad=self.page_settings.chk_vad.isChecked(),
                min_silence_ms=self.page_settings.silence_spin.value(), # [FIX MEDIUM #11]
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

            # [FIX HIGH #3] Áp dụng Guard Hardsub cho cả nhánh Existing SRT
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
        
        if self.ai_panel.mode_combo.currentData() == "timing":
            # [FIX] Tự động nạp kết quả Timing vào Editor và Video Player
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
            
        # Kiểm tra cờ thiết lập Hardsub
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
        
        # [FIX] Bổ sung reset cho thanh progress của Dashboard
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

        # [FIX HIGH] Dọn dẹp triệt để UI khi chết ở item cuối cùng
        self._cleanup_ui_after_task()

    def _cleanup_ui_after_task(self):
        """Đưa toàn bộ thanh Progress và Label hệ thống về trạng thái mặc định (Idle)"""
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
        """Khởi động luồng AI Batch Fill và reset thanh tiến độ."""
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
        # Reset Progress Bars trước khi chạy tác vụ mới
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
        """Cập nhật dữ liệu vào Editor, lưu Checkpoint vào đĩa và trả trạng thái tiến độ về an toàn."""
        for start_ms, end_ms, text, stt in filled_segments:
            for seg in self.sub_editor.all_segments:
                if str(seg['stt']) == str(stt):
                    seg['text'] = text
                    seg['status'] = 'draft'
                    break

        self.sub_editor.render_page()
        self.sub_editor.update_draft_progress()

        # Đảm bảo lưu đúng file draft gắn với video hiện tại
        draft_file = self.sub_editor.save_draft(silent=True)
        if draft_file:
            self.queue_mgr.set_srt_for_video(self.queue_mgr.active_vid, draft_file)

        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.ai_panel.set_state("COMPLETED", "Điền chữ hoàn tất!")

        # [CHÈN VỊ TRÍ 3.2 TẠI ĐÂY]
        self.ai_panel.lbl_batch_stat.setText(f"Batch Progress: Hoàn tất {len(filled_segments)} segments")
        
        # [FIX] Đưa thanh tiến độ về 0 sau 2.5 giây thay vì kẹt 100% vĩnh viễn
        self.progress_bar.setValue(100)
        self.ai_panel.progress_bar.setValue(100)
        QTimer.singleShot(2500, self._reset_progress_state)
        
        Toast.show_success(self, "Đã điền chữ AI hoàn tất lượt Batch!")

    def _reset_progress_state(self):
        """Khôi phục các thanh tiến độ và nhãn trạng thái về Idle."""
        if not hasattr(self, 'worker') or not self.worker.isRunning():
            self.progress_bar.setValue(0)
            self.ai_panel.progress_bar.setValue(0)
            # [FIX] Bổ sung reset cho thanh progress của Dashboard
            self.page_dashboard.quick_progress.setValue(0) 
            
            self.lbl_speed_eta.setText("Speed: 0.0x | ETA: --")
            if self.ai_panel.state == "COMPLETED":
                self.ai_panel.set_state("READY", "Sẵn sàng cho tác vụ tiếp theo")   

    def closeEvent(self, event):
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
            
        # [FIX MEDIUM #5] Bọc try-except bắt lỗi phân quyền/filesystem khi tạo thư mục
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            Toast.show_error(self, f"Lỗi hệ thống tập tin: {str(e)}")
            return

        base_name = os.path.splitext(os.path.basename(self.queue_mgr.active_vid))[0]
        exported = []

        # [FIX HIGH #1] Import đúng path module của Core
        try:
            from core.subtitle_exporter import SubtitleExportService
            exporter = SubtitleExportService()
        except ImportError:
            Toast.show_error(self, "Lỗi nạp SubtitleExportService từ core. Kiểm tra lại module.")
            return

        # [FIX HIGH #2] Ép kiểu từ Data Model của UI (List Dict) sang Data Model của Core (List Tuples, ms)
        subtitles_for_export = []
        for seg in self.sub_editor.all_segments:
            start_ms = self.sub_editor.time_str_to_ms(seg["start"])
            end_ms = self.sub_editor.time_str_to_ms(seg["end"])
            text = seg["text"] if seg["text"] != "[ Chưa có nội dung ]" else ""
            subtitles_for_export.append((start_ms, end_ms, text))

        # [FIX MEDIUM #5] Bọc try-except toàn bộ quá trình xuất file
        try:
            if self.page_export.chk_srt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.srt")
                exporter.export_srt(subtitles_for_export, path)
                exported.append("SRT")
            
            if self.page_export.chk_vtt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.vtt")
                exporter.export_vtt(subtitles_for_export, path)
                exported.append("VTT")

            if self.page_export.chk_txt.isChecked():
                path = os.path.join(out_dir, f"{base_name}.txt")
                exporter.export_txt(subtitles_for_export, path)
                exported.append("TXT")

            if exported:
                Toast.show_success(self, f"Đã xuất thành công: {', '.join(exported)}")
            else:
                Toast.show_info(self, "Vui lòng chọn ít nhất một định dạng xuất.")
        except Exception as e:
            Toast.show_error(self, f"Lỗi trong quá trình ghi file: {str(e)}")

    def _retry_current_task(self):
        # [FIX MEDIUM #4] Khôi phục lại trạng thái và chạy lại Item vừa bị lỗi
        self.ai_panel.set_state("READY", "Đang thử lại...")
        if hasattr(self, 'current_batch_index') and self.current_batch_index > 0:
            self.current_batch_index -= 1
            self.batch_queue.insert(0, (self.current_vid, self.queue_mgr.get_items()[self.current_vid].get("srt_path")))
            self.process_next_batch_item()
        elif hasattr(self, 'queue_mgr') and self.queue_mgr.active_vid:
            self.start_processing()

    def _continue_draft_from_center(self, draft_path):
        """Nạp Draft, tự động chọn và cuộn tới dòng trống đầu tiên để người dùng chủ động chạy."""
        # [FIX] Đặt silent=True để triệt tiêu Toast "Đã nạp bản nháp", chống đè thông báo
        if not self._load_draft_from_center(draft_path, silent=True):
            return

        # Quét tìm vị trí câu trống đầu tiên (rỗng hoặc mang placeholder)
        start_idx = None
        for i, seg in enumerate(self.sub_editor.all_segments):
            text = str(seg.get('text', '')).strip()
            if not text or text == "[ Chưa có nội dung ]":
                start_idx = i
                break
                
        if start_idx is None:
            Toast.show_success(self, "Bản nháp này đã hoàn tất 100% nội dung.")
            return

        # Cuộn và chọn dòng trống để người dùng dễ quan sát
        if self.sub_editor.table.rowCount() > start_idx:
            item = self.sub_editor.table.item(start_idx, 0)
            if item:
                self.sub_editor.table.scrollToItem(item)
                self.sub_editor.table.selectRow(start_idx)

        Toast.show_info(self, f"Đã định vị đến câu {start_idx + 1}. Bạn có thể kiểm tra và bấm bắt đầu khi sẵn sàng.")


if __name__ == "__main__":
    # Kích hoạt chuẩn High DPI cho Windows để tránh bị mờ hoặc scale sai lệch
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())