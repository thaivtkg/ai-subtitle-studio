import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class HardsubConfirmDialog(QDialog):
    # Các hằng số kết quả trả về
    HARDSUB = 1
    EDIT = 2
    SKIP = 3

    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hoàn tất tạo Phụ đề")
        self.setModal(True) # Chặn thao tác với cửa sổ chính khi Dialog đang mở
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        
        self.setStyleSheet("""
            QDialog { 
                background-color: #161B26; 
                border: 1px solid #35C8FF; 
                border-radius: 8px; 
            }
            QLabel { color: #F5F7FA; font-size: 13px; }
            QPushButton { 
                font-weight: bold; border-radius: 6px; 
                padding: 8px 16px; border: none; font-size: 12px;
            }
            QPushButton#btn_hardsub { background-color: #35C8FF; color: #0D111A; }
            QPushButton#btn_hardsub:hover { background-color: #6CD0FF; }
            
            QPushButton#btn_edit { background-color: #2B3547; color: #FFFFFF; border: 1px solid #35C8FF; }
            QPushButton#btn_edit:hover { background-color: #38455A; }
            
            QPushButton#btn_skip { background-color: transparent; color: #98A2B3; text-decoration: underline; }
            QPushButton#btn_skip:hover { color: #FFFFFF; }
        """)

        # Mặc định an toàn: Nếu user ấn X hoặc ESC, tương đương Bỏ qua (SKIP)
        self.user_choice = self.SKIP
        video_name = os.path.basename(video_path) if video_path else "Video"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)

        # Tiêu đề
        lbl_title = QLabel("✨ Trích xuất Phụ đề thành công!")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #33D17A; margin-bottom: 5px;")
        
        # Nội dung
        lbl_msg = QLabel(f"File SRT cho video <b>{video_name}</b> đã được tạo xong.<br><br>Bạn muốn thực hiện bước tiếp theo là gì?")
        lbl_msg.setWordWrap(True)

        # Hàng Nút bấm
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_hardsub = QPushButton("🎬 Chèn Hardsub ngay")
        btn_hardsub.setObjectName("btn_hardsub")
        btn_hardsub.setCursor(Qt.PointingHandCursor)
        btn_hardsub.clicked.connect(self.choose_hardsub)
        
        btn_edit = QPushButton("📝 Chỉnh sửa Subtitle")
        btn_edit.setObjectName("btn_edit")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.choose_edit)
        
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_hardsub)

        # Nút Bỏ qua (Nằm ở dưới cùng)
        btn_skip = QPushButton("Bỏ qua (Giữ nguyên SRT)")
        btn_skip.setObjectName("btn_skip")
        btn_skip.setCursor(Qt.PointingHandCursor)
        btn_skip.clicked.connect(self.choose_skip)

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_msg)
        layout.addLayout(btn_layout)
        layout.addWidget(btn_skip, alignment=Qt.AlignCenter)

    def choose_hardsub(self):
        self.user_choice = self.HARDSUB
        self.accept() # Đóng dialog và trả về QDialog.Accepted

    def choose_edit(self):
        self.user_choice = self.EDIT
        self.accept()

    def choose_skip(self):
        self.user_choice = self.SKIP
        self.reject() # Đóng dialog và trả về QDialog.Rejected