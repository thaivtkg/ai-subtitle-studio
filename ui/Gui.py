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

from player.video_player import VideoPlayerWidget
from ui.SubEditor import SubtitleEditorWidget
from utils import load_settings, save_settings
from workers.TaskQueue import AdvancedWorkerThread

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
        self.resize(1100, 720)
        self.setStyleSheet(DARK_STUDIO_QSS)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.old_pos = QPoint()
        self.file_pairs = {}
        self.active_vid = None
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
        sidebar_frame.setFixedWidth(260)
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
        self.right_splitter.setStyleSheet("QSplitter::handle { background: #273247; height: 3px; }")

        # --- NỬA TRÊN: VIDEO PLAYER ---
        self.video_player = VideoPlayerWidget()
        self.video_player.setMinimumHeight(250)
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

        self.bottom_tabs.addTab(self.sub_editor, "📝 Subtitle Editor")

        # Tab 2: Video Queue & Output (Đóng gói Queue cũ vào một Widget)
        queue_wrapper = QWidget()
        queue_wrapper_layout = QVBoxLayout(queue_wrapper)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setAlignment(Qt.AlignTop)
        self.queue_layout.setSpacing(4)
        self.scroll_area.setWidget(self.queue_container)

        output_layout = QHBoxLayout()
        self.out_input = QLineEdit()
        self.out_input.setPlaceholderText("Thư mục lưu kết quả mặc định...")
        out_btn = QPushButton("Browse...")
        out_btn.setObjectName("btn_secondary")
        out_btn.clicked.connect(self.select_output_dir)
        output_layout.addWidget(QLabel("Output:"))
        output_layout.addWidget(self.out_input)
        output_layout.addWidget(out_btn)

        queue_wrapper_layout.addWidget(self.scroll_area)
        queue_wrapper_layout.addLayout(output_layout)
        self.bottom_tabs.addTab(queue_wrapper, "📋 Video Queue")

        # Tab 3: Live Log
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Nhật ký trạng thái hoạt động...")
        self.bottom_tabs.addTab(self.log_box, "📜 Live Log")

        self.right_splitter.addWidget(self.bottom_tabs)

        # Mặc định chia tỷ lệ: Video chiếm 45%, Panel dưới chiếm 55%
        self.right_splitter.setSizes([450, 550])

        middle_layout.addWidget(self.right_splitter, stretch=1)


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

        self.refresh_queue_ui()
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
        # Lấy danh sách toàn bộ các file được thả vào
        urls = event.mimeData().urls()
        
        # Danh sách đuôi video hợp lệ
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')
        
        has_new_file = False # Cờ kiểm tra xem có file mới được thêm vào không
        
        for url in urls:
            file_path = url.toLocalFile()
            
            # Kiểm tra nếu đúng là file video thì mới xử lý
            if file_path.lower().endswith(valid_extensions):
                # Thêm vào danh sách file_pairs nếu chưa tồn tại
                if file_path not in self.file_pairs:
                    self.file_pairs[file_path] = None
                    has_new_file = True
        
        # Nếu có ít nhất 1 file hợp lệ được kéo vào, làm mới lại giao diện Video Queue
        if has_new_file:
            self.refresh_queue_ui()

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
        if not settings: return # Nếu chưa có cài đặt thì bỏ qua

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

    def select_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if files:
            for f in files:
                if f not in self.file_pairs: 
                    self.file_pairs[f] = None
                    last_added = f
            self.refresh_queue_ui()
            # [Tính năng mới] Tự động chuyển sang video vừa thêm
            if last_added:
                self.on_queue_item_clicked(last_added, self.file_pairs[last_added])

    def select_srt_for_video(self):
        video_path, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Media (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if video_path:
            srt_path, _ = QFileDialog.getOpenFileName(self, "Chọn file SRT", "", "Subtitle (*.srt)")
            if srt_path:
                self.file_pairs[video_path] = srt_path
                self.refresh_queue_ui()

                # [Tính năng mới] Tự động load ngay cặp Video + SRT vừa chọn
                self.on_queue_item_clicked(video_path, srt_path)

    def clear_files(self):
        self.file_pairs.clear()
        self.refresh_queue_ui()

    def select_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục đầu ra")
        if d: self.out_input.setText(d)

    def refresh_queue_ui(self):
        while self.queue_layout.count():
            item = self.queue_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for vid, srt in self.file_pairs.items():
            card = QFrame()

            # Kiểm tra xem card này có phải là video đang active không
            is_active = (vid == getattr(self, 'active_vid', None))

            if is_active:
                # Đang chọn: Nền sáng hơn, viền xanh nhạt cố định
                card.setStyleSheet("""
                            QFrame { background-color: #1A212E; border: 1px solid #35C8FF; border-radius: 6px; }
                        """)
            else:
                # Bình thường: Nền tối, hover mới sáng
                card.setStyleSheet("""
                            QFrame { background-color: #10141F; border: 1px solid #273247; border-radius: 6px; }
                            QFrame:hover { border: 1px solid #35C8FF; background-color: #161B26; }
                        """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)

            # --- BƯỚC 1: BẮT SỰ KIỆN CLICK CHUỘT VÀO QUEUE ĐỂ LOAD VIDEO ---
            card.setCursor(Qt.PointingHandCursor)  # Đổi con trỏ chuột thành hình bàn tay
            card.mousePressEvent = lambda event, v=vid, s=srt: self.on_queue_item_clicked(v, s)
            # ---------------------------------------------------------------

            file_name = os.path.basename(vid)
            status_text = f"SRT: {os.path.basename(srt)}" if srt else "Waiting (AI large-v3)"
            info_label = QLabel(f"🎬  <b>{file_name}</b><br><span style='color: #98A2B3;'>{status_text}</span>")

            # Bỏ qua sự kiện click của Label để click xuyên qua QFrame bên dưới
            info_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            card_layout.addWidget(info_label, stretch=4)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(24, 24)
            btn_del.setStyleSheet("background: #273247; border-radius: 4px; color: #FF5C73; font-weight: bold;")
            btn_del.clicked.connect(lambda checked=False, v=vid: self.remove_single_file(v))
            card_layout.addWidget(btn_del)
            self.queue_layout.addWidget(card)

        count = len(self.file_pairs)
        self.lbl_queue_val.setText(f"{count} video" if count <= 1 else f"{count} videos")

        # --- BƯỚC 2: TỰ ĐỘNG LOAD VIDEO ĐẦU TIÊN NẾU PLAYER ĐANG TRỐNG ---
        if count > 0:
            first_vid = list(self.file_pairs.keys())[0]
            first_srt = self.file_pairs[first_vid]
            # Kiểm tra xem Player đã load file nào chưa
            if hasattr(self, 'video_player') and self.video_player.player.source().isEmpty():
                self.on_queue_item_clicked(first_vid, first_srt)
        else:
            # Nếu xóa hết video trong Queue thì dọn dẹp màn hình Player
            if hasattr(self, 'video_player'):
                self.video_player.cleanup()

    def remove_single_file(self, vid_path):
        if vid_path in self.file_pairs:
            del self.file_pairs[vid_path]
            self.refresh_queue_ui()

    def start_processing(self):
        if not self.file_pairs: return

        tasks = list(self.file_pairs.items())
        output_dir = self.out_input.text().strip()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_box.clear()
        
        self.lbl_status_val.setText("Processing")
        self.lbl_status_val.setStyleSheet("color: #F5B942; font-size: 12px; font-weight: bold;")

        self.worker = AdvancedWorkerThread(
            tasks, output_dir, self.prompt_input.text().strip(), 0.0, 
            self.chk_hardsub.isChecked(), self.size_spin.value(), "white", 
            self.font_combo.currentText(), self.compute_combo.currentData(), # Thay currentData bằng currentText cho font
            self.chk_vad.isChecked(), self.spin_silence.value(),model_size=self.model_combo.currentData()
        )
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.error_signal.connect(self.process_error)
        self.worker.start()

    def cancel_processing(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.append_log("[HỆ THỐNG] Đang hủy tiến trình an toàn...")
            self.cancel_btn.setEnabled(False)

    def update_progress(self, val, msg):
        # Kích hoạt Animation trượt mượt mà thay vì nhảy cóc
        self.progress_anim.stop()
        self.progress_anim.setStartValue(self.progress_bar.value())
        self.progress_anim.setEndValue(val)
        self.progress_anim.start()

    def append_log(self, msg):
        self.log_box.append(msg)
        
        # Chỉ cập nhật speed từ FFmpeg nếu có
        speed_match = re.search(r"speed=\s*([0-9\.]+x)", msg)
        if speed_match:
            self.lbl_speed_eta.setText(f"Speed: {speed_match.group(1)}")

    def process_finished(self, msg):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.lbl_status_val.setText("Idle")
        self.lbl_status_val.setStyleSheet("color: #33D17A; font-size: 12px; font-weight: bold;")
        # --- THÊM ĐOẠN NÀY ĐỂ RESET THANH TIẾN ĐỘ ---
        self.progress_anim.stop()           # Dừng hiệu ứng chạy mượt
        self.progress_bar.setValue(0)       # Trả thanh % về 0
        self.lbl_speed_eta.setText("Speed: 0.0x  |  ETA: --") # Reset text tốc độ
        # ---------------------------------------------
        QMessageBox.information(self, "Hoàn tất", msg)

    def process_error(self, err):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.lbl_status_val.setText("Idle")
        self.lbl_status_val.setStyleSheet("color: #33D17A; font-size: 12px; font-weight: bold;")
        # --- THÊM ĐOẠN NÀY ĐỂ RESET THANH TIẾN ĐỘ ---
        self.progress_anim.stop()
        self.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("Speed: 0.0x  |  ETA: --")
        # ---------------------------------------------
        QMessageBox.critical(self, "Lỗi", err)

    def open_subtitle_editor(self):
        if not self.file_pairs: return
        
        # [Tối ưu] Xác định đúng video đang được Active. Nếu không có mới lấy video đầu tiên
        vid = getattr(self, 'active_vid', None)
        if not vid or vid not in self.file_pairs:
            vid = list(self.file_pairs.keys())[0]
            
        srt = self.file_pairs[vid]

        # Tạo file SRT ảo nếu video chưa có
        if not srt or not os.path.exists(srt):
            base = os.path.splitext(vid)[0]
            srt = f"{base}.srt"
            if not os.path.exists(srt):
                with open(srt, "w", encoding="utf-8") as f:
                    f.write("1\n00:00:00,000 --> 00:00:05,000\n[AI Subtitle Studio Placeholder]\n")
            self.file_pairs[vid] = srt
            self.refresh_queue_ui()

        # [Tối ưu] Thay vì chỉ load SRT vào Editor, gọi lệnh nạp đồng bộ cả Player và Controller
        self.on_queue_item_clicked(vid, srt)

    def open_output_folder(self):
        out_d = self.out_input.text().strip()
        if not out_d and self.file_pairs:
            out_d = os.path.dirname(list(self.file_pairs.keys())[0])
        if out_d and os.path.exists(out_d):
            os.startfile(out_d)

    def closeEvent(self, event):
        # --- THÊM ĐOẠN LƯU CÀI ĐẶT TRƯỚC KHI TẮT APP ---
        settings = {
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
        # -----------------------------------------------
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

    def on_queue_item_clicked(self, vid_path, srt_path):
        self.active_vid = vid_path

        # --- BƯỚC QUAN TRỌNG NHẤT ĐỂ SỬA LỖI ---
        # 1. Bắt buộc gọi lệnh nạp video TRƯỚC để Player ghi nhận là đã có file
        self.video_player.load_video(vid_path)

        # 2. SAU ĐÓ mới làm mới Queue UI để đổi viền sáng (Ngăn chặn vòng lặp vô hạn)
        self.refresh_queue_ui()
        # ---------------------------------------

        # 3. Nạp SRT vào Bảng Editor và não SubtitleController
        if srt_path and os.path.exists(srt_path):
            self.sub_editor.load_srt_file(srt_path)
            self.video_player.sub_controller.load_srt(srt_path)
        else:
            self.sub_editor.table.setRowCount(0)
            self.video_player.sub_controller.load_srt(None)

        self.bottom_tabs.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
