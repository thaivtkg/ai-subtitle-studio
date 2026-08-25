import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QMessageBox
)
from ui.theme import Theme

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tạo Dự Án Mới")
        self.setFixedSize(500, 250)
        self.setStyleSheet(f"background-color: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY};")
        layout = QVBoxLayout(self)
        
        # 1. Tên dự án
        layout.addWidget(QLabel("Tên dự án:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("VD: Video Highlight LMHT")
        layout.addWidget(self.name_input)
        
        # 2. File Video Gốc
        layout.addWidget(QLabel("File Video gốc (.mp4, .mkv):"))
        video_layout = QHBoxLayout()
        self.video_input = QLineEdit()
        self.video_input.setReadOnly(True)
        btn_browse_video = QPushButton("Chọn File...")
        btn_browse_video.clicked.connect(self._browse_video)
        video_layout.addWidget(self.video_input)
        video_layout.addWidget(btn_browse_video)
        layout.addLayout(video_layout)
        
        # 3. Thư mục lưu Project
        layout.addWidget(QLabel("Thư mục lưu trữ Project:"))
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setReadOnly(True)
        btn_browse_dir = QPushButton("Chọn Thư mục...")
        btn_browse_dir.clicked.connect(self._browse_dir)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(btn_browse_dir)
        layout.addLayout(dir_layout)
        
        # Nút Tạo / Hủy
        btn_layout = QHBoxLayout()
        btn_create = QPushButton("🚀 Khởi tạo Dự án")
        btn_create.setStyleSheet(f"background-color: {Theme.PRIMARY_PURPLE}; padding: 8px; font-weight: bold;")
        btn_create.clicked.connect(self._validate_and_accept)
        
        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_create)
        layout.addLayout(btn_layout)

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Video Nguồn", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        if path:
            self.video_input.setText(path)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn Thư mục lưu Project")
        if path:
            self.dir_input.setText(path)

    def _validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên dự án!")
            return
        if not self.video_input.text() or not os.path.exists(self.video_input.text()):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một file video hợp lệ!")
            return
        if not self.dir_input.text() or not os.path.exists(self.dir_input.text()):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu trữ hợp lệ!")
            return
            
        self.accept()
        
    def get_project_data(self):
        return {
            "name": self.name_input.text().strip(),
            "video_path": self.video_input.text(),
            "project_dir": self.dir_input.text()
        }