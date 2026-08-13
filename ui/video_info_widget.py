import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt

class VideoInfoWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #161B26; border: 1px solid #273247; border-radius: 6px;")
        
        # [FIX] Tăng min-height của cả Panel để chịu tải được các Label bên trong
        self.setMinimumHeight(165)
        
        layout = QVBoxLayout(self)
        # [FIX] Tăng margin đáy lên 16px để tạo khoảng thở an toàn cho viền đáy
        layout.setContentsMargins(15, 12, 15, 16)
        layout.setSpacing(6)
        
        title = QLabel("ℹ️ VIDEO INFORMATION")
        title.setStyleSheet("color: #35C8FF; font-weight: bold; font-size: 12px; border: none;")
        title.setMinimumHeight(20) # [FIX] Ép bằng API C++
        layout.addWidget(title)
        
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(8) # Tăng nhẹ khoảng cách dọc để chữ không bị dí sát
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
        lbl_title.setStyleSheet("color: #98A2B3; border: none; font-weight: bold;")
        # [FIX BLOCKER] Ép buộc Qt Layout Engine cấp phát đúng 22px chiều cao
        lbl_title.setMinimumHeight(22) 
        
        lbl_value = QLabel("--")
        lbl_value.setStyleSheet("color: #F5F7FA; border: none;")
        lbl_value.setWordWrap(True)
        # [FIX BLOCKER] Ép buộc Qt Layout Engine cấp phát đúng 22px chiều cao
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