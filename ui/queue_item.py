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
        self.setFixedHeight(60) # Thu gọn chiều cao vì đã gom chung một dòng
        
        self.init_ui(status, has_srt, duration)
        self.update_style()

    def init_ui(self, status, has_srt, duration):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(4)

        # Hàng 1: Tên file & Nút Remove
        top_layout = QHBoxLayout()
        file_name = os.path.basename(self.vid_path) if self.vid_path else "Unknown"
        self.lbl_name = QLabel(f"🎬 <b>{file_name}</b>")
        self.lbl_name.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setStyleSheet("background: transparent; color: #FF5C73; font-weight: bold; border: none;")
        self.btn_remove.clicked.connect(lambda: self.remove_signal.emit(self.vid_path))
        
        top_layout.addWidget(self.lbl_name, stretch=1)
        top_layout.addWidget(self.btn_remove)
        
        # Hàng 2: Gom toàn bộ Status, AI/SRT và Duration vào 1 dòng tinh gọn
        bottom_layout = QHBoxLayout()
        self.lbl_details = QLabel()
        self.lbl_details.setStyleSheet("color: #98A2B3; font-size: 11px;")
        self.lbl_details.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.update_details_text(status, has_srt, duration)
        
        bottom_layout.addWidget(self.lbl_details)
        bottom_layout.addStretch()

        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)

    def update_details_text(self, status, has_srt, duration):
        # [UX Fix] Dùng dấu bullet (•) để ngăn cách tạo cảm giác pro, không rườm rà
        status_icon = "🟢" if status == "Ready" else "🟡"
        srt_icon = "📝 Có sẵn SRT" if has_srt else "🤖 Cần AI"
        self.lbl_details.setText(f"{status_icon} {status}   •   {srt_icon}   •   ⏱ {duration}")

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