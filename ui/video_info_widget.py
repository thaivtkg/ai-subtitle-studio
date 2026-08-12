import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt

class VideoInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #10141F; border: 1px solid #273247; border-radius: 6px;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title = QLabel("ℹ️ VIDEO INFORMATION")
        title.setStyleSheet("color: #35C8FF; font-weight: bold; font-size: 13px; border: none;")
        layout.addWidget(title)
        
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        
        self.labels = {}
        self._add_info_row(0, "Tên:")
        self._add_info_row(1, "Định dạng:")
        self._add_info_row(2, "Thời lượng:")
        self._add_info_row(3, "Resolution:")
        self._add_info_row(4, "FPS:")
        self._add_info_row(5, "Audio:")
        self._add_info_row(6, "Subtitle:")
        self._add_info_row(7, "File size:")
        
        layout.addLayout(self.grid)
        layout.addStretch()

    def _add_info_row(self, row, label_text):
        lbl_title = QLabel(label_text)
        lbl_title.setStyleSheet("color: #98A2B3; border: none; font-weight: bold;")
        
        lbl_value = QLabel("--")
        lbl_value.setStyleSheet("color: #F5F7FA; border: none;")
        lbl_value.setWordWrap(True)
        
        self.grid.addWidget(lbl_title, row, 0, Qt.AlignTop)
        self.grid.addWidget(lbl_value, row, 1, Qt.AlignTop)
        self.labels[label_text] = lbl_value

    def update_info(self, vid_path, metadata, srt_path):
        # [Safety] Xử lý an toàn khi None input
        if not vid_path or not metadata:
            self.clear_info()
            return

        self.labels["Tên:"].setText(os.path.basename(vid_path))
        self.labels["Định dạng:"].setText(metadata.get("format", "--"))
        self.labels["Thời lượng:"].setText(metadata.get("duration", "--:--:--"))
        self.labels["Resolution:"].setText(metadata.get("resolution", "--"))
        self.labels["FPS:"].setText(metadata.get("fps", "--"))
        self.labels["Audio:"].setText(metadata.get("audio", "--"))
        self.labels["File size:"].setText(metadata.get("size", "--"))

        if srt_path and os.path.exists(srt_path):
            try:
                # Tránh parse kỹ, chỉ đếm số block phụ đề để tối ưu tốc độ
                with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                    blocks = f.read().strip().split('\n\n')
                    # Loại trừ block rỗng do \n\n dư thừa
                    valid_blocks = [b for b in blocks if len(b) > 0]
                    self.labels["Subtitle:"].setText(f"Có — {len(valid_blocks)} dòng")
            except Exception:
                self.labels["Subtitle:"].setText("Có — Lỗi đọc file")
        else:
            self.labels["Subtitle:"].setText("Không có")

    def clear_info(self):
        for lbl in self.labels.values():
            lbl.setText("--")