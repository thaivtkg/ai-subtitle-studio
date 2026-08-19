import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt

# Nạp Design System
from ui.theme import Theme

class HardsubConfirmDialog(QDialog):
    # Các hằng số lựa chọn (Khớp với logic bên Gui.py)
    HARDSUB = 1
    EDIT = 2
    SKIP = 3

    def __init__(self, vid_path, parent=None):
        super().__init__(parent)
        self.vid_path = vid_path
        self.user_choice = self.SKIP # Mặc định là bỏ qua nếu user tắt ngang

        # Cấu hình Dialog không viền (Frameless) và nền trong suốt
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(480)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container chính để bo góc và đổ màu
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE_ELEVATED};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)

        # Tiêu đề
        title = QLabel("🎬 Xác nhận Hardsub")
        title.setStyleSheet(f"color: {Theme.CYAN}; font-size: 16px; font-weight: bold; border: none;")
        container_layout.addWidget(title)

        # Nội dung thông báo
        file_name = os.path.basename(self.vid_path) if self.vid_path else "Video"
        msg = QLabel(
            f"Quá trình tạo phụ đề cho <b>{file_name}</b> đã hoàn tất!<br><br>"
            f"Bạn có muốn chèn cứng phụ đề (Hardsub) vào video ngay bây giờ, "
            f"hay tạm dừng tiến trình để chỉnh sửa lại bản nháp?"
        )
        msg.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; border: none; line-height: 1.5;")
        msg.setWordWrap(True)
        container_layout.addWidget(msg)

        # Đường phân cách
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {Theme.BORDER}; border: none;")
        container_layout.addWidget(sep)

        # Hàng nút bấm hành động
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # 1. Nút Bỏ qua (Danger / Muted)
        btn_skip = QPushButton("Bỏ qua")
        btn_skip.setCursor(Qt.PointingHandCursor)
        btn_skip.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {Theme.TEXT_MUTED}; 
                font-weight: bold; border-radius: 6px; padding: 8px 16px; border: 1px solid {Theme.BORDER};
            }}
            QPushButton:hover {{ 
                background-color: {Theme.DANGER}; color: #FFFFFF; border: 1px solid {Theme.DANGER}; 
            }}
        """)
        btn_skip.clicked.connect(self.choose_skip)

        # 2. Nút Chỉnh sửa (Secondary)
        btn_edit = QPushButton("📝 Chỉnh sửa")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE_SOFT}; color: {Theme.CYAN}; 
                font-weight: bold; border-radius: 6px; padding: 8px 16px; border: 1px solid {Theme.CYAN};
            }}
            QPushButton:hover {{ 
                background-color: {Theme.CYAN}; color: #0D111A; 
            }}
        """)
        btn_edit.clicked.connect(self.choose_edit)

        # 3. Nút Hardsub (Primary - Nổi bật nhất)
        btn_hardsub = QPushButton("✅ Chèn Hardsub")
        btn_hardsub.setCursor(Qt.PointingHandCursor)
        btn_hardsub.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.PRIMARY_GRADIENT};
                color: #FFFFFF; font-weight: bold; border-radius: 6px; padding: 8px 16px; border: none;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #A78BFA, stop: 1 #F472B6);
            }}
        """)
        btn_hardsub.clicked.connect(self.choose_hardsub)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_skip)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_hardsub)

        container_layout.addLayout(btn_layout)
        layout.addWidget(container)

    # --- Các hàm tín hiệu ---
    def choose_hardsub(self):
        self.user_choice = self.HARDSUB
        self.accept()

    def choose_edit(self):
        self.user_choice = self.EDIT
        self.accept()

    def choose_skip(self):
        self.user_choice = self.SKIP
        self.reject()