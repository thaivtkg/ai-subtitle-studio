import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class QueueItemWidget(QFrame):
    clicked_signal = Signal(str)
    remove_signal = Signal(str)

    def __init__(self, vid_path, status, has_srt, duration, parent=None):
        super().__init__(parent)
        self.vid_path = vid_path
        self.is_active = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(80)
        
        self.init_ui(status, has_srt, duration)
        self.update_style()

    def init_ui(self, status, has_srt, duration):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Hàng trên: Tên file và nút Xóa
        top_layout = QHBoxLayout()
        # [Safety] Xử lý an toàn nếu vid_path bị rỗng
        file_name = os.path.basename(self.vid_path) if self.vid_path else "Unknown"
        self.lbl_name = QLabel(f"🎬 <b>{file_name}</b>")
        self.lbl_name.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setStyleSheet("background: transparent; color: #FF5C73; font-weight: bold; border: none;")
        self.btn_remove.clicked.connect(lambda: self.remove_signal.emit(self.vid_path))
        
        top_layout.addWidget(self.lbl_name, stretch=1)
        top_layout.addWidget(self.btn_remove)
        
        # Hàng dưới: Trạng thái, SRT, Thời lượng
        bottom_layout = QHBoxLayout()
        
        status_icon = "🟢" if status == "Ready" else "🟡"
        self.lbl_status = QLabel(f"{status_icon} {status}")
        self.lbl_status.setStyleSheet("color: #98A2B3; font-size: 11px;")
        
        srt_text = "📝 Có sẵn SRT" if has_srt else "🤖 Cần AI"
        srt_color = "#33D17A" if has_srt else "#F5B942"
        self.lbl_srt = QLabel(srt_text)
        self.lbl_srt.setStyleSheet(f"color: {srt_color}; font-size: 11px; font-weight: bold;")
        
        self.lbl_duration = QLabel(f"⏱ {duration}")
        self.lbl_duration.setStyleSheet("color: #98A2B3; font-size: 11px;")
        
        bottom_layout.addWidget(self.lbl_status)
        bottom_layout.addWidget(self.lbl_srt)
        bottom_layout.addWidget(self.lbl_duration)
        bottom_layout.addStretch()

        # [UX] Chặn sự kiện chuột của Label để QFrame bắt được sự kiện Click
        for lbl in [self.lbl_status, self.lbl_srt, self.lbl_duration]:
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)

    def set_active(self, active):
        if self.is_active != active:
            self.is_active = active
            self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QueueItemWidget { background-color: #1A212E; border: 1px solid #35C8FF; border-radius: 6px; }
            """)
        else:
            self.setStyleSheet("""
                QueueItemWidget { background-color: #10141F; border: 1px solid #273247; border-radius: 6px; }
                QueueItemWidget:hover { border: 1px solid #35C8FF; background-color: #161B26; }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_signal.emit(self.vid_path)
        super().mousePressEvent(event)