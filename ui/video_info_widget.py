import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt

# Nạp Design System
from ui.theme import Theme

class VideoInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # [S6-FIX] Giao diện Card Panel chuẩn xác
        self.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px;")
        self.setMinimumHeight(165)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(6)
        
        title = QLabel("ℹ️ VIDEO METADATA")
        title.setStyleSheet(f"color: {Theme.CYAN}; font-weight: bold; font-size: 12px; border: none;")
        title.setMinimumHeight(20)
        layout.addWidget(title)
        
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(8)
        self.grid.setHorizontalSpacing(15)
        
        self.labels = {}
        # Hàng 1
        self._add_info_cell(0, 0, "Tên:")
        self._add_info_cell(0, 2, "Resolution:")
        # Hàng 2
        self._add_info_cell(1, 0, "Định dạng:")
        self._add_info_cell(1, 2, "FPS:")
        # Hàng 3
        self._add_info_cell(2, 0, "Thời lượng:")
        self._add_info_cell(2, 2, "Audio:")
        # Hàng 4
        self._add_info_cell(3, 0, "Subtitle:")
        self._add_info_cell(3, 2, "File size:")
        
        layout.addLayout(self.grid)
        layout.addStretch()

    def _add_info_cell(self, row, col, label_text):
        lbl_title = QLabel(label_text)
        # [S6-FIX] Tiêu đề nhạt, nội dung sáng chuẩn Typography
        lbl_title.setStyleSheet(f"color: {Theme.TEXT_MUTED}; border: none; font-weight: bold; font-size: 12px;")
        lbl_title.setMinimumHeight(22) 
        
        lbl_value = QLabel("--")
        lbl_value.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: none; font-weight: 500; font-size: 12px;")
        lbl_value.setWordWrap(True)
        lbl_value.setMinimumHeight(22) 
        
        self.grid.addWidget(lbl_title, row, col)
        self.grid.addWidget(lbl_value, row, col + 1)
        
        self.grid.setColumnStretch(col + 1, 1) 
        self.labels[label_text] = lbl_value

    def update_info(self, vid_path, metadata, srt_path):
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
                with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
                    blocks = f.read().strip().split('\n\n')
                    valid_blocks = [b for b in blocks if len(b) > 0]
                    self.labels["Subtitle:"].setText(f"Có — {len(valid_blocks)} dòng")
            except Exception:
                self.labels["Subtitle:"].setText("Có — Lỗi đọc file")
        else:
            self.labels["Subtitle:"].setText("Không có")

    def clear_info(self):
        for lbl in self.labels.values():
            lbl.setText("--")