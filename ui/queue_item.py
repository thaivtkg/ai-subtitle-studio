import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

# Nạp Design System
from ui.theme import Theme

class QueueItemWidget(QFrame):
    clicked_signal = Signal(str)
    remove_signal = Signal(str)

    def __init__(self, vid_path, status, has_srt, duration, parent=None):
        super().__init__(parent)
        self.vid_path = vid_path
        self.is_active = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64) # Tăng nhẹ chiều cao để Card thoáng hơn
        
        self.init_ui(status, has_srt, duration)
        self.update_style()

    def init_ui(self, status, has_srt, duration):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        # Hàng 1: Tên file & Nút Remove
        top_layout = QHBoxLayout()
        file_name = os.path.basename(self.vid_path) if self.vid_path else "Unknown"
        self.lbl_name = QLabel(f"🎬 <b>{file_name}</b>")
        self.lbl_name.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; border: none;")
        self.lbl_name.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip("Xóa video khỏi hàng đợi")
        self.btn_remove.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Theme.TEXT_MUTED}; font-weight: bold; border: none; font-size: 14px; border-radius: 4px; }}
            QPushButton:hover {{ color: #FFFFFF; background: {Theme.DANGER}; }}
        """)
        self.btn_remove.clicked.connect(lambda: self.remove_signal.emit(self.vid_path))
        
        top_layout.addWidget(self.lbl_name, stretch=1)
        top_layout.addWidget(self.btn_remove)
        
        # Hàng 2: Gom toàn bộ Status, AI/SRT và Duration thành dạng Badge Text
        bottom_layout = QHBoxLayout()
        self.lbl_details = QLabel()
        self.lbl_details.setStyleSheet("border: none;")
        self.lbl_details.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.update_details_text(status, has_srt, duration)
        
        bottom_layout.addWidget(self.lbl_details)
        bottom_layout.addStretch()

        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)

    def update_details_text(self, status, has_srt, duration):
        # [S6-FIX] Phân loại màu sắc huy hiệu (Badge) bằng HTML Rich Text
        status_color = Theme.SUCCESS if status == "Ready" else Theme.WARNING
        status_html = f"<span style='color: {status_color}; font-weight: bold;'>● {status}</span>"
        
        srt_color = Theme.CYAN if has_srt else Theme.TEXT_MUTED
        srt_text = "📝 Có sẵn Phụ đề / Draft" if has_srt else "🤖 Chờ xử lý AI"
        srt_html = f"<span style='color: {srt_color};'>{srt_text}</span>"
        
        dur_html = f"<span style='color: {Theme.TEXT_MUTED};'>⏱ {duration}</span>"
        
        self.lbl_details.setText(f"{status_html} &nbsp;&nbsp;|&nbsp;&nbsp; {srt_html} &nbsp;&nbsp;|&nbsp;&nbsp; {dur_html}")

    def set_active(self, active):
        if self.is_active != active:
            self.is_active = active
            self.update_style()

    def update_style(self):
        # [S6-FIX] Thiết kế Active Card nổi bật với viền trái dày màu tím Gradient
        if self.is_active:
            self.setStyleSheet(f"""
                QueueItemWidget {{ 
                    background-color: {Theme.SURFACE_SOFT}; 
                    border: 1px solid {Theme.PRIMARY_PURPLE}; 
                    border-left: 4px solid {Theme.PRIMARY_PURPLE}; 
                    border-radius: 6px; 
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QueueItemWidget {{ 
                    background-color: {Theme.SURFACE_ELEVATED}; 
                    border: 1px solid {Theme.BORDER}; 
                    border-radius: 6px; 
                }}
                QueueItemWidget:hover {{ 
                    border: 1px solid {Theme.CYAN}; 
                    background-color: {Theme.SURFACE_SOFT}; 
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_signal.emit(self.vid_path)
        super().mousePressEvent(event)