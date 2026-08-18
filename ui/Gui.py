import os
import re
import sys

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
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
from utils import load_settings, save_settings
from workers.TaskQueue import HardsubWorker, WhisperWorker

DARK_STUDIO_QSS = """
QMainWindow {
    background-color: #0D111A;
}
QWidget {
    color: #F5F7FA;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 12px;
}
QScrollBar:vertical {
    background: #0D111A;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #273247;
    min-height: 20px;
    border-radius: 3px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #161B26;
    border: 1px solid #273247;
    border-radius: 5px;
    padding: 4px 8px;
    color: #F5F7FA;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #35C8FF;
}
QTextEdit {
    background-color: #10141F;
    border: 1px solid #273247;
    border-radius: 6px;
    color: #98A2B3;
    font-family: 'Consolas', monospace;
    font-size: 12px;
    padding: 6px;
}
QPushButton#SideBtn {
    background-color: #161B26;
    border: 1px solid #273247;
    border-radius: 6px;
    color: #F5F7FA;
    text-align: left;
    padding-left: 10px;
    font-weight: 600;
    min-height: 34px;
}
QPushButton#SideBtn:hover {
    border: 1px solid #35C8FF;
    color: #35C8FF;
}
/* =========================================
   1. NÚT PRIMARY (Gradient - Start Batch)
   ========================================= */
QPushButton#btn_primary {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #4AC1FF, stop: 1 #8A75FF);
    color: #FFFFFF;
    font-weight: bold;
    border-radius: 6px;
    border: none;
    padding: 8px 16px;
}
QPushButton#btn_primary:hover {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #6CD0FF, stop: 1 #9E8DFF);
}
QPushButton#btn_primary:pressed {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #3399D4, stop: 1 #6854CC);
    padding-top: 10px; 
    padding-bottom: 6px;
}

/* =========================================
   2. NÚT DANGER (Đỏ - Cancel, X)
   ========================================= */
QPushButton#btn_danger {
    background-color: #FF1F1F;
    color: #FFFFFF;
    font-weight: bold;
    border-radius: 6px;
    border: none;
    padding: 8px 16px;
}
QPushButton#btn_danger:hover {
    background-color: #FF758F;
}
QPushButton#btn_danger:pressed {
    background-color: #D6425C;
    padding-top: 10px;
    padding-bottom: 6px;
}

/* =========================================
   3. NÚT SECONDARY (Tối màu - Browse, Mở thư mục)
   ========================================= */
QPushButton#btn_secondary {
    background-color: #2B3547;
    color: #FFFFFF;
    font-weight: bold;
    border-radius: 6px;
    border: 1px solid #1E2532;
    padding: 8px 16px;
}
QPushButton#btn_secondary:hover {
    background-color: #38455A;
    border: 1px solid #4AC1FF;
}
QPushButton#btn_secondary:pressed {
    background-color: #1A212E;
    border: 1px solid #1A212E;
    padding-top: 10px;
    padding-bottom: 6px;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Subtitle Studio")
        self.setMinimumSize(1024, 700)
        self.resize(1100, 720)
        self.setStyleSheet(DARK_STUDIO_QSS)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.old_pos = QPoint()
        self.queue_mgr = QueueManager()
        self.queue_mgr.queue_updated.connect(self.on_queue_updated)

        # [Fix] Đón Signal Highlight giao diện
        self.queue_mgr.active_changed.connect(
            lambda vid: self.queue_ui.sync_with_manager(self.queue_mgr.get_items(), vid)
        )

        self.queue_mgr.item_removed.connect(self.on_queue_item_removed_handler)

        self.setAcceptDrops(True)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Thanh tiêu đề giả lập
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(4, 0, 4, 0)
        logo_label = QLabel("✨ AI Subtitle Studio (Borderless)")
        logo_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #35C8FF;")
        title_bar.addWidget(logo_label)
        title_bar.addStretch()
        
        btn_minimize = QPushButton("—")
        btn_minimize.setFixedSize(28, 24)
        btn_minimize.setStyleSheet("background: #161B26; color: #FFF; border: none; border-radius: 4px;")
        btn_minimize.clicked.connect(self.showMinimized)
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 24)
        btn_close.setStyleSheet("background: #FF5C73; color: #0D111A; font-weight: bold; border: none; border-radius: 4px;")
        btn_close.clicked.connect(self.close)

        title_bar.addWidget(btn_minimize)
        title_bar.addWidget(btn_close)
        main_layout.addLayout(title_bar)

        # Dashboard AI
        dash_frame = QFrame()
        dash_frame.setStyleSheet("background-color: #161B26; border: 1px solid #273247; border-radius: 8px;")
        dash_layout = QHBoxLayout(dash_frame)
        dash_layout.setContentsMargins(10, 8, 10, 8)
        
        self.lbl_gpu_val, card_gpu = self.create_metric_widget("GPU", "Detecting...", "#35C8FF")
        self.lbl_vram_val, card_vram = self.create_metric_widget("VRAM", "-- / -- GB", "#7B61FF")
        self.lbl_cpu_val, card_cpu = self.create_metric_widget("CPU", "0%", "#35C8FF")
        self.lbl_lang_val, card_lang = self.create_metric_widget("Language", "Auto", "#F5F7FA")
        self.lbl_queue_val, card_queue = self.create_metric_widget("Queue", "0 video", "#35C8FF")
        self.lbl_status_val, card_status = self.create_metric_widget("Status", "Idle", "#33D17A")

        dash_layout.addWidget(card_gpu)
        dash_layout.addWidget(card_vram)
        dash_layout.addWidget(card_cpu)
        dash_layout.addWidget(card_lang)
        dash_layout.addWidget(card_queue)
        dash_layout.addWidget(card_status)
        main_layout.addWidget(dash_frame)

        # Khu vực giữa (Middle Section)
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)

        # Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setStyleSheet("background-color: #161B26; border: 1px solid #273247; border-radius: 8px;")
        sidebar_frame.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(6)

        sidebar_layout.addWidget(self.create_side_button("📂  Add Video...", self.select_videos))
        sidebar_layout.addWidget(self.create_side_button("📝  Add SRT for Video...", self.select_srt_for_video))
        sidebar_layout.addWidget(self.create_side_button("✨  Edit Selected SRT", self.open_subtitle_editor))
        sidebar_layout.addWidget(self.create_side_button("🗑  Clear Queue", self.clear_files))
        
        settings_label = QLabel("⚙  AI & Hardsub Settings")
        settings_label.setStyleSheet("font-weight: bold; color: #35C8FF; margin-top: 4px;")
        sidebar_layout.addWidget(settings_label)

        ai_form_layout = QVBoxLayout()
        ai_form_layout.setSpacing(4)

        # --- BẮT ĐẦU THÊM: [P2-T2] CHỌN CHẾ ĐỘ XỬ LÝ (MODE) ---
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Full Subtitle (AI sinh Text)", "full")
        self.mode_combo.addItem("Timing Draft (Chỉ tạo khung thời gian)", "timing")
        self.mode_combo.setStyleSheet("QComboBox { font-weight: bold; color: #35C8FF; }")
        
        ai_form_layout.addWidget(QLabel("Chế độ xử lý (Pipeline Mode):"))
        ai_form_layout.addWidget(self.mode_combo)

        self.mode_combo.currentIndexChanged.connect(
            lambda: self.chk_hardsub.setEnabled(self.mode_combo.currentData() == "full")
        )

        # --- KẾT THÚC THÊM ---

        # --- THÊM PHẦN CHỌN MODEL Ở ĐÂY ---
        self.model_combo = QComboBox()
        self.model_combo.addItem("Large V3 Turbo (Khuyên dùng - Nhanh)", "large-v3-turbo")
        self.model_combo.addItem("Large V3 (Chuẩn gốc)", "large-v3")
        ai_form_layout.addWidget(QLabel("Whisper Model Size:"))
        ai_form_layout.addWidget(self.model_combo)
        # ----------------------------------
        
        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Float16 (RTX 4060)", "float16")
        self.compute_combo.addItem("Int8_Float16 (Save VRAM)", "int8_float16")
        ai_form_layout.addWidget(QLabel("AI Model & VRAM:"))
        ai_form_layout.addWidget(self.compute_combo)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Context / Prompt...")
        ai_form_layout.addWidget(self.prompt_input)

        vad_layout = QHBoxLayout()
        self.chk_vad = QCheckBox("VAD Filter")
        self.chk_vad.toggled.connect(lambda c: self.spin_silence.setEnabled(c))
        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(100, 2000)
        self.spin_silence.setValue(500)
        self.spin_silence.setEnabled(False)
        vad_layout.addWidget(self.chk_vad)
        vad_layout.addWidget(self.spin_silence)
        ai_form_layout.addLayout(vad_layout)

        self.chk_hardsub = QCheckBox("Chèn Hardsub tự động")
        self.chk_hardsub.setChecked(True)
        ai_form_layout.addWidget(self.chk_hardsub)

        style_row = QHBoxLayout()
        self.font_combo = QComboBox()
        font = self.font_combo.font()
        font.setPointSize(10) # Bắt buộc phải set cứng một số > 0
        self.font_combo.setFont(font)
        for f in ["Noto Sans JP", "Arial", "Segoe UI"]: self.font_combo.addItem(f, f)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 72)
        self.size_spin.setValue(42)
        style_row.addWidget(self.font_combo)
        style_row.addWidget(self.size_spin)
        ai_form_layout.addLayout(style_row)

        sidebar_layout.addLayout(ai_form_layout)
        sidebar_layout.addStretch()
        middle_layout.addWidget(sidebar_frame)

        # Right Panel (Sử dụng QSplitter để chia đôi linh hoạt)
        self.right_splitter = QSplitter(Qt.Vertical)
        # [FIX UX] Thêm margin cho thanh kéo Splitter để tạo khoảng hở trên/dưới an toàn
        self.right_splitter.setStyleSheet("QSplitter::handle { background: #273247; height: 1px; margin: 1px 0px; }")

        # --- NỬA TRÊN: VIDEO PLAYER ---
        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(250)
        
        # [FIX BLOCKER] Bơm thêm 12px đệm ở đáy Video Player để bảo vệ thanh Control (Play, Time) khỏi bị cắt xén
        self.video_player.setContentsMargins(0, 0, 0, 12)
        
        self.right_splitter.addWidget(self.video_player)

        # --- NỬA DƯỚI: TABS (Subtitle, Queue, Log) ---
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid #273247; border-radius: 4px; background: #161B26; }
                    QTabBar::tab { background: #10141F; color: #98A2B3; padding: 6px 16px; border: 1px solid #273247; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }
                    QTabBar::tab:selected { background: #35C8FF; color: #0D111A; }
                    QTabBar::tab:hover:!selected { background: #1E2532; color: #FFF; }
                """)

        # Tab 1: Subtitle Editor
        self.sub_editor = SubtitleEditorWidget()
        self.sub_editor.seek_requested.connect(self.video_player.set_position)
        self.video_player.sub_controller.subtitle_cleared.connect(self.sub_editor.clear_highlight)

        # --- BẮT ĐẦU SỬA KHU VỰC NÀY ---
        # 1. Cập nhật màu trên bảng khi tới câu mới
        self.video_player.sub_controller.subtitle_changed.connect(
            lambda stt, start, text: self.sub_editor.highlight_row_by_stt(stt)
        )
        # --- THÊM PHẦN KẾT NỐI MỚI ---
        # 2. Toggle Bật/Tắt chữ trên Video
        self.sub_editor.preview_toggled.connect(self.video_player.sub_controller.toggle_preview)

        # 3. Apply Style đổi theo thời gian thực lên Video Overlay
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
        # -----------------------------

        # --- THÊM PHẦN NÀY: 4. Đồng bộ Real-time từ Bảng sang Lõi Controller ---
        self.sub_editor.live_edit_applied.connect(self.video_player.sub_controller.update_live_data)
        # -----------------------------------------------------------------------

        # [P2-T9] Kích hoạt luồng AI Điền Chữ khi bấm Nút "Chốt Timing"
        self.sub_editor.fill_text_requested.connect(self.start_fill_text_worker)

        self.bottom_tabs.addTab(self.sub_editor, "📝 Subtitle Editor")

        # Tab 2: Video Queue & Output
        queue_wrapper = QWidget()
        queue_wrapper_layout = QVBoxLayout(queue_wrapper)

        self.queue_ui = QueueWidget()
        self.queue_ui.item_clicked.connect(self.on_queue_item_clicked)
        self.queue_ui.item_removed.connect(self.queue_mgr.remove_video)
        queue_wrapper_layout.addWidget(self.queue_ui)

        output_layout = QHBoxLayout()
        self.out_input = QLineEdit()
        self.out_input.setPlaceholderText("Thư mục lưu kết quả mặc định...")
        out_btn = QPushButton("Browse...")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(QLabel("Output:"))
        output_layout.addWidget(self.out_input)
        output_layout.addWidget(out_btn)

        queue_wrapper_layout.addLayout(output_layout)
        self.bottom_tabs.addTab(self.queue_ui, "📋 Video Queue")

        # [FIX BLOCKER #2] ĐÃ XÓA ĐOẠN ĐẦU NỐI DUPLICATE BỊ LẶP 2 LẦN Ở ĐÂY

        # Tab 3: Live Log
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái hoạt động...")
        self.bottom_tabs.addTab(self.log_box, "📜 Live Log")

        self.right_splitter.addWidget(self.bottom_tabs)

        # =========================================================================
        # [FIX BLOCKER] Ép Splitter ưu tiên 100% không gian thừa cho Video Player (Stretch=1).
        # Ép cụm Tabs giữ nguyên kích thước tối thiểu, không được tự phình to (Stretch=0).
        # =========================================================================
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 0)
        self.right_splitter.setSizes([450, 200]) # Cấp mồi 450px cho Video Player để nó không bị ép lúc mở App

        # [FIX UX] Bọc nửa bên phải vào một Container (Hộp chứa) riêng.
        # Giúp thanh Output không bị tràn sang cắn lẹm vào phần Sidebar bên trái.
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        right_layout.addWidget(self.right_splitter, stretch=1)

        # === BẮT ĐẦU: GLOBAL OUTPUT FOLDER ===
        output_layout = QHBoxLayout()
        output_layout.setContentsMargins(4, 0, 4, 0)
        
        lbl_out = QLabel("📁 Output Folder:")
        lbl_out.setStyleSheet("font-weight: bold; color: #98A2B3; font-size: 12px;")
        
        self.out_input = QLineEdit()
        self.out_input.setPlaceholderText("Thư mục lưu kết quả xuất video...")
        
        out_btn = QPushButton("Browse...")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self.select_output_dir)
        
        output_layout.addWidget(lbl_out)
        output_layout.addWidget(self.out_input)
        output_layout.addWidget(out_btn)
        
        # Nhét thanh Output vào dưới cùng của hộp chứa bên phải
        right_layout.addLayout(output_layout)
        # =============================================================

        # Nạp hộp chứa bên phải vào Layout ngang ở giữa
        middle_layout.addWidget(right_container, stretch=1)
        main_layout.addLayout(middle_layout)

        # === BẮT ĐẦU: THÊM LẠI THANH TIẾN ĐỘ Ở NGAY TRÊN NÚT START ===
        prog_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #161B26; border: 1px solid #273247;
                        border-radius: 5px; text-align: center; color: #F5F7FA; height: 16px;
                    }
                    QProgressBar::chunk {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #35C8FF, stop:1 #7B61FF);
                        border-radius: 4px;
                    }
                """)
        self.progress_anim = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_anim.setDuration(400)

        self.lbl_speed_eta = QLabel("Speed: 0.0x  |  ETA: --")
        self.lbl_speed_eta.setStyleSheet("color: #98A2B3; font-weight: bold; font-size: 11px;")

        prog_layout.addWidget(self.progress_bar, stretch=4)
        prog_layout.addWidget(self.lbl_speed_eta, stretch=1)
        main_layout.addLayout(prog_layout)
        # === KẾT THÚC: THÊM LẠI THANH TIẾN ĐỘ ===

        # Bottom Control Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.start_btn = QPushButton("Start Batch")
        self.start_btn.setObjectName("btn_primary")
        self.start_btn.clicked.connect(self.start_processing)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("btn_danger")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setObjectName("btn_secondary")
        open_folder_btn.clicked.connect(self.open_output_folder)

        bottom_bar.addWidget(self.start_btn, stretch=3)
        bottom_bar.addWidget(self.cancel_btn, stretch=1)
        bottom_bar.addWidget(open_folder_btn, stretch=1)
        main_layout.addLayout(bottom_bar)

        self.on_queue_updated()
        self.update_hardware_info()
        self.update_cpu_usage()

        # --- THÊM ĐOẠN KHÔI PHỤC CÀI ĐẶT TỪ JSON ---
        self.apply_saved_settings()
        # ------------------------------------------
        
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_hardware_info)
        self.stats_timer.timeout.connect(self.update_cpu_usage)
        self.stats_timer.start(1000)

        # --- THÊM DÒNG NÀY: ÉP ĐỒNG BỘ STYLE NGAY KHI MỞ APP ---
        self.sub_editor.emit_style()
        # -------------------------------------------------------

        

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def dragEnterEvent(self, event):
        # Chỉ chấp nhận nếu dữ liệu kéo vào là đường dẫn (file/thư mục)
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

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def create_metric_widget(self, title, value, color):
        frame = QFrame()
        frame.setStyleSheet("background: #10141F; border: 1px solid #273247; border-radius: 5px; padding: 2px 8px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        
        lbl_title = QLabel(title)
        # Sửa lỗi font size -1 bằng cách đẩy kích thước lên 10px
        lbl_title.setStyleSheet("color: #98A2B3; font-size: 10px; font-weight: bold;")
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return lbl_val, frame

    def apply_saved_settings(self):
        settings = load_settings()
        if not settings: return 

        # [P2-T2] Khôi phục Chế độ xử lý (Pipeline Mode)
        if "mode" in settings:
            idx = self.mode_combo.findData(settings["mode"])
            if idx >= 0: self.mode_combo.setCurrentIndex(idx)

        # Khôi phục Model Whisper
        if "model_size" in settings:
            idx = self.model_combo.findData(settings["model_size"])
            if idx >= 0: self.model_combo.setCurrentIndex(idx)
            
        # Khôi phục Compute Type (VRAM)
        if "compute_type" in settings:
            idx = self.compute_combo.findData(settings["compute_type"])
            if idx >= 0: self.compute_combo.setCurrentIndex(idx)
            
        # Khôi phục Prompt, Font, Hardsub
        if "prompt" in settings: self.prompt_input.setText(settings["prompt"])
        if "font_name" in settings: self.font_combo.setCurrentText(settings["font_name"])
        if "font_size" in settings: self.size_spin.setValue(settings["font_size"])
        if "do_hardsub" in settings: self.chk_hardsub.setChecked(settings["do_hardsub"])
        
        # Khôi phục VAD
        if "use_vad" in settings: self.chk_vad.setChecked(settings["use_vad"])
        if "silence_ms" in settings: self.spin_silence.setValue(settings["silence_ms"])
        
        # Khôi phục Thư mục Output
        if "output_dir" in settings: self.out_input.setText(settings["output_dir"])

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

    def create_side_button(self, text, slot):
        btn = QPushButton(text)
        btn.setObjectName("SideBtn")
        btn.clicked.connect(slot)
        return btn

    def _start_metadata_worker(self, video_paths):
        if not video_paths:
            return
            
        # [Predictive Fix] Dùng List để giữ reference, chống Python thu hồi RAM (GC) làm chết Worker ngầm
        if not hasattr(self, 'meta_workers'):
            self.meta_workers = []

        worker = MetadataWorker(video_paths)
        worker.metadata_parsed.connect(self.queue_mgr.update_metadata)
        
        # Tự động tự hủy reference khi Worker chạy xong
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
            
            # Khởi chạy Worker ngầm cho các file vừa thêm (Chống đơ UI)
            self._start_metadata_worker(added_files)
            
            if added_files:
                self.on_queue_item_clicked(added_files[-1])

    def select_srt_for_video(self):
        video_path, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if video_path:
            # [P2-T10] Mở rộng bộ lọc cho phép nạp cả file Draft
            srt_path, _ = QFileDialog.getOpenFileName(self, "Chọn file Phụ đề / Draft", "", "Subtitle & Draft (*.srt *.ai-subtitle-draft)")
            if srt_path:
                if video_path not in self.queue_mgr.get_items():
                    self.queue_mgr.add_video(video_path)
                    self._start_metadata_worker([video_path])
                    
                self.queue_mgr.set_srt_for_video(video_path, srt_path)
                self.on_queue_item_clicked(video_path)

    # def clear_files(self):
    #     self.queue_mgr.clear_queue()
    #     # [Clear All Requirements] Đảm bảo dọn dẹp Player, Editor và Overlay
    #     self.video_player.cleanup()
    #     self.video_player.sub_controller.load_srt(None)
    #     self.sub_editor.table.setRowCount(0)  

    def clear_files(self):
        # [Fix] Chỉ ra lệnh xóa Data Model. UI sẽ tự động dọn dẹp thông qua Signal
        self.queue_mgr.clear_queue()

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục đầu ra")
        if d: self.out_input.setText(d)

    # --- HÀM MỚI THAY THẾ refresh_queue_ui ---
    def on_queue_updated(self):
        items = self.queue_mgr.get_items()
        self.queue_ui.sync_with_manager(items, self.queue_mgr.active_vid)
        
        count = len(items)
        self.lbl_queue_val.setText(f"{count} video" if count <= 1 else f"{count} videos")
        
        # [Fix Blocker] Đã xóa đoạn IF auto-load video gây vòng lặp đệ quy. 
        # Chỉ dọn dẹp màn hình nếu Queue rỗng.
        if count == 0:
            if hasattr(self, 'video_player'):
                self.video_player.cleanup()
                self.video_player.sub_controller.load_srt(None)
            if hasattr(self, 'sub_editor'):
                self.sub_editor.table.setRowCount(0)

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
        self.log_box.clear()
        
        self.lbl_status_val.setText("Processing")
        self.lbl_status_val.setStyleSheet("color: #F5B942; font-size: 12px; font-weight: bold;")
        
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
            # Tình huống 1: Chưa có SRT -> Chạy AI Whisper
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
            # Tình huống 2: ĐÃ CÓ SẴN SRT (Vừa chỉnh sửa xong hoặc Import tay)
            self.append_log(f"[HỆ THỐNG] Phát hiện file SRT có sẵn: {current_srt}")
            if self.chk_hardsub.isChecked():
                # [FIX BLOCKER UX] Bỏ qua Hộp thoại xác nhận, Render luôn để đảm bảo tự động hóa Batch!
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
        
        # [FIX TIMING WORKFLOW] Nếu là Timing Draft, chuyển thẳng sang Editor để kiểm duyệt
        if self.mode_combo.currentData() == "timing":
            self.append_log("[HỆ THỐNG] Đã tạo xong Timing Artifact. Chuyển sang Subtitle Editor để kiểm duyệt...")
            self.on_queue_item_clicked(self.current_vid)
            self.bottom_tabs.setCurrentIndex(0)
            self.process_finished("Đã tạo xong khung thời gian (Timing Draft)! Vui lòng kiểm duyệt trên Editor.")
            return

        # Với Full Subtitle: Hỏi xác nhận Hardsub nếu có bật tùy chọn
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
            # [FIX BLOCKER] Chuyển Tab và Load Subtitle mà không làm kẹt luồng UI
            self.bottom_tabs.setCurrentIndex(0)
            self.on_queue_item_clicked(vid_path)
            
            # Reset UI như hàm Finished nhưng không văng Pop-up block
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.lbl_status_val.setText("Idle")
            self.lbl_status_val.setStyleSheet("color: #33D17A; font-size: 12px; font-weight: bold;")
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
        
        # Mở khóa các nút điều khiển trong Subtitle Editor đề phòng trường hợp Cancel/Error
        if hasattr(self, 'sub_editor'):
            if hasattr(self.sub_editor, 'fill_text_btn'):
                self.sub_editor.fill_text_btn.setEnabled(True)
            if hasattr(self.sub_editor, 'save_btn'):
                self.sub_editor.save_btn.setEnabled(True)

        self.lbl_status_val.setText("Idle")
        self.lbl_status_val.setStyleSheet("color: #33D17A; font-size: 12px; font-weight: bold;")
        self.progress_anim.stop()
        self.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("Speed: 0.0x  |  ETA: --")
        
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Trạng thái", msg)

    def process_error(self, err):
        self.append_log(f"❌ [LỖI] {err}")
        # [FIX] Nhận diện thông báo Hủy để Log chính xác
        if getattr(self, 'is_cancelled_flag', False) or "hủy" in str(err).lower():
            self.process_finished("Tiến trình đã bị dừng.")
        elif hasattr(self, 'batch_queue') and len(self.batch_queue) > 0:
            self.append_log("[HỆ THỐNG] Bỏ qua video lỗi, tiếp tục với video tiếp theo trong Queue...")
            self.process_next_batch_item()
        else:
            self.process_finished("Tiến trình hoàn tất (có phát sinh lỗi ở file cuối).")

    def open_subtitle_editor(self):
        if not self.queue_mgr.get_items(): return
        
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

        self.on_queue_item_clicked(vid)

    def open_output_folder(self):
        out_d = self.out_input.text().strip()
        items = self.queue_mgr.get_items()
        if not out_d and items:
            out_d = os.path.dirname(list(items.keys())[0])
            
        if out_d and os.path.exists(out_d):
            os.startfile(out_d)

    def closeEvent(self, event):
        # [P2-T2] Lưu cài đặt bao gồm cả "mode" trước khi đóng App
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

        import subprocess
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
            # [P2-T10] Phân luồng đọc theo Định dạng đuôi file
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
            # [FIX] Ép buộc QMediaPlayer cắt đứt hoàn toàn File Source đang giữ
            try:
                from PySide6.QtCore import QUrl
                self.video_player.player.stop()
                self.video_player.player.setSource(QUrl())
            except Exception:
                pass
            
            self.video_player.cleanup()
            self.video_player.sub_controller.load_srt(None)
            self.sub_editor.table.setRowCount(0)
        else:
            if self.queue_mgr.active_vid:
                self.on_queue_item_clicked(self.queue_mgr.active_vid)

    # =========================================================================
    # ĐIỀU PHỐI LUỒNG FILL TEXT WORKER (P2-T9) & PHÂN TRANG (P2-T7)
    # =========================================================================
    def start_fill_text_worker(self):
        if not self.queue_mgr.active_vid:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn video cần điền chữ.")
            return
            
        # [P2-T7] Lấy toàn bộ dữ liệu trực tiếp từ Model thay vì Table giao diện
        segments = []
        for seg in self.sub_editor.all_segments:
            start_ms = self.sub_editor.time_str_to_ms(seg['start'])
            end_ms = self.sub_editor.time_str_to_ms(seg['end'])
            raw_text = seg['text']
            if raw_text == "[ Chưa có nội dung ]": raw_text = ""
            try: stt = int(seg['stt'])
            except: stt = 0
            
            segments.append((start_ms, end_ms, raw_text, stt))
                
        if not segments: 
            return
        
        self.is_cancelled_flag = False
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.sub_editor.fill_text_btn.setEnabled(False)
        self.sub_editor.save_btn.setEnabled(False)
        
        self.bottom_tabs.setCurrentIndex(2) 
        self.append_log(f"\n[HỆ THỐNG] Bắt đầu chốt Timing và Điền chữ cho {len(segments)} câu...")
        
        from workers.TaskQueue import FillTextWorker
        self.worker = FillTextWorker(
            video_path=self.queue_mgr.active_vid,
            segments_data=segments,
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
        self.bottom_tabs.setCurrentIndex(0)
        
        # [P2-T7] Điền trực tiếp kết quả Text AI trả về vào Model Tổng
        for row, (start_ms, end_ms, text, stt) in enumerate(filled_segments):
            if row < len(self.sub_editor.all_segments):
                self.sub_editor.all_segments[row]['text'] = text
        
        # Ra lệnh cho Giao diện Vẽ lại trang hiện tại và Đồng bộ với Video Controller
        self.sub_editor.render_page()
        
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_anim.stop()
        self.progress_bar.setValue(100)
        self.lbl_speed_eta.setText("Điền chữ thành công! Hãy ấn Lưu (Ctrl+S).")
        self.sub_editor.fill_text_btn.setEnabled(True)
        self.sub_editor.save_btn.setEnabled(True)
        
        QMessageBox.information(self, "Thành công", "Đã điền chữ xong! Vui lòng ấn 'Lưu thay đổi (Ctrl+S)' để lưu kết quả vào file.")
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


