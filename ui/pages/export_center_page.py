from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import Theme


class ExportCenterPage(QWidget):
    export_srt_requested = Signal()
    burn_hardsub_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("🚀 Export & Delivery Center")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; border: none;")
        layout.addWidget(title)

        # 1. Format Selection Card
        fmt_frame = QFrame()
        fmt_frame.setStyleSheet(f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 14px;")
        fmt_layout = QVBoxLayout(fmt_frame)
        fmt_layout.setSpacing(10)

        lbl_f_title = QLabel("Định dạng xuất phụ đề (Softsub):")
        lbl_f_title.setStyleSheet(f"font-weight: bold; color: {Theme.CYAN}; border: none;")
        fmt_layout.addWidget(lbl_f_title)

        self.chk_srt = QCheckBox("SubRip Subtitle (*.srt) — Chuẩn phát hành quốc tế")
        self.chk_srt.setChecked(True)
        self.chk_vtt = QCheckBox("WebVTT (*.vtt) — Chuẩn Web & HTML5 Video")
        self.chk_txt = QCheckBox("Plain Text (*.txt) — Bản gỡ băng thuần văn bản")

        fmt_layout.addWidget(self.chk_srt)
        fmt_layout.addWidget(self.chk_vtt)
        fmt_layout.addWidget(self.chk_txt)
        layout.addWidget(fmt_frame)

        # 2. Hardsub Options Card
        hs_frame = QFrame()
        hs_frame.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 14px;")
        hs_layout = QVBoxLayout(hs_frame)
        hs_layout.setSpacing(10)

        lbl_hs_title = QLabel("Xuất Video Hardsub (FFmpeg GPU Acceleration):")
        lbl_hs_title.setStyleSheet(f"font-weight: bold; color: {Theme.CYAN}; border: none;")
        hs_layout.addWidget(lbl_hs_title)

        self.chk_hardsub = QCheckBox("Render MP4 Hardsub (Chèn cứng phụ đề vào video)")
        self.chk_hardsub.setChecked(True)
        hs_layout.addWidget(self.chk_hardsub)
        layout.addWidget(hs_frame)

        # 3. Output Directory
        out_frame = QFrame()
        out_frame.setStyleSheet(f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 12px;")
        out_layout = QHBoxLayout(out_frame)
        out_layout.setSpacing(8)

        lbl_out = QLabel("📁 Thư mục lưu:")
        lbl_out.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: bold; border: none;")
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Đường dẫn lưu trữ kết quả...")
        btn_browse = QPushButton("Chọn...")
        btn_browse.setObjectName("btn_secondary")
        btn_browse.clicked.connect(self._select_dir)

        out_layout.addWidget(lbl_out)
        out_layout.addWidget(self.out_edit, stretch=1)
        out_layout.addWidget(btn_browse)
        layout.addWidget(out_frame)

        layout.addStretch()

        # Action Buttons
        act_row = QHBoxLayout()
        act_row.setSpacing(10)

        btn_exp_sub = QPushButton("💾 Xuất file Phụ đề (Softsub)")
        btn_exp_sub.setObjectName("btn_secondary")
        btn_exp_sub.clicked.connect(self.export_srt_requested.emit)

        btn_exp_video = QPushButton("🎬 Render Video Hardsub")
        btn_exp_video.setObjectName("btn_primary")
        btn_exp_video.clicked.connect(self.burn_hardsub_requested.emit)

        act_row.addWidget(btn_exp_sub)
        act_row.addWidget(btn_exp_video, stretch=1)
        layout.addLayout(act_row)

    def _select_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất kết quả")
        if d:
            self.out_edit.setText(d)