from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.services.hardware_checker import HardwareChecker, HardwareProfile
from ui.theme import Theme


class HardwareCheckDialog(QDialog):
    """Detailed hardware compatibility and model recommendation modal."""

    apply_recommended = Signal(str, str)

    def __init__(self, parent=None, profile: HardwareProfile = None):
        super().__init__(parent)
        self.setWindowTitle("Chi tiết kiểm tra cấu hình máy & Đề xuất AI")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.profile = profile or HardwareChecker.detect()
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Theme.BG_APP}; color: {Theme.TEXT_PRIMARY}; }}
            QLabel {{ color: {Theme.TEXT_PRIMARY}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        lbl_title = QLabel("💻 Kiểm tra cấu hình & Khả năng chạy Model")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {Theme.CYAN};")
        layout.addWidget(lbl_title)

        # Summary box
        summary_frame = QFrame()
        summary_frame.setStyleSheet(
            f"background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.BORDER}; "
            f"border-radius: 8px; padding: 6px;"
        )
        s_layout = QVBoxLayout(summary_frame)
        s_layout.setSpacing(6)

        gpu_text = f"{self.profile.gpu_name} ({self.profile.total_vram_gb} GB VRAM)" if self.profile.has_cuda else "CPU Mode (Không phát hiện CUDA)"
        lbl_hw = QLabel(f"<b>Thiết bị:</b> {gpu_text} | <b>RAM:</b> {self.profile.ram_gb} GB | <b>CPU:</b> {self.profile.cpu_cores} cores")
        lbl_hw.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_PRIMARY};")
        s_layout.addWidget(lbl_hw)

        status_color = Theme.SUCCESS if "Mượt" in self.profile.stability_rating else (Theme.CYAN if "Ổn" in self.profile.stability_rating else Theme.WARNING)
        lbl_rating = QLabel(
            f"<b>Đánh giá máy:</b> <span style='color: {status_color}; font-weight: 700;'>{self.profile.stability_rating}</span> · "
            f"<b>Đề xuất:</b> <span style='color: {Theme.CYAN}; font-weight: 700;'>{self.profile.recommended_model} ({self.profile.recommended_compute})</span>"
        )
        lbl_rating.setStyleSheet("font-size: 12px;")
        s_layout.addWidget(lbl_rating)

        layout.addWidget(summary_frame)

        # Checks list scroll area
        lbl_list_title = QLabel("Chi tiết khả năng chạy các tính năng & model:")
        lbl_list_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {Theme.TEXT_SECONDARY};")
        layout.addWidget(lbl_list_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        for c in self.profile.checks:
            row = QFrame()
            row.setStyleSheet(
                f"background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; "
                f"border-radius: 6px; padding: 4px;"
            )
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(10, 8, 10, 8)
            r_layout.setSpacing(12)

            icon_lbl = QLabel("✅" if c.get("can_run") else "⚠️")
            icon_lbl.setStyleSheet("font-size: 14px;")
            r_layout.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            name_lbl = QLabel(f"<b>{c.get('feature', '')}</b>")
            name_lbl.setStyleSheet("font-size: 12px;")
            detail_lbl = QLabel(c.get("detail", ""))
            detail_lbl.setStyleSheet(f"font-size: 11px; color: {Theme.TEXT_MUTED};")
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(detail_lbl)
            r_layout.addLayout(info_layout, stretch=1)

            scroll_layout.addWidget(row)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Buttons footer
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_apply = QPushButton(f"✨ Áp dụng đề xuất ({self.profile.recommended_model})")
        btn_apply.setFixedHeight(32)
        btn_apply.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.PRIMARY_PURPLE}; color: #ffffff; "
            f"border: none; border-radius: 6px; padding: 6px 16px; font-weight: 700; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.CYAN}; }}"
        )
        btn_apply.clicked.connect(self._on_apply_clicked)
        btn_row.addWidget(btn_apply)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; padding: 6px 16px; font-size: 12px; }} "
            f"QPushButton:hover {{ background-color: {Theme.SURFACE_SOFT}; }}"
        )
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_apply_clicked(self):
        self.apply_recommended.emit(self.profile.recommended_model, self.profile.recommended_compute)
        self.accept()
