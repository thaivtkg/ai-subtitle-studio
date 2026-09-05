from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ui.theme import Theme


class FirstRunBanner(QWidget):
    """Non-blocking first-run invitation banner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("first_run_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#first_run_banner {{ background-color: {Theme.SURFACE_ELEVATED}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; "
            f"color: {Theme.TEXT_PRIMARY}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(QLabel("Chào mừng bạn! Khám phá hướng dẫn sử dụng nhanh.", self))
        layout.addStretch()
        self.start_btn = QPushButton("Bắt đầu hướng dẫn", self)
        self.dismiss_btn = QPushButton("Để sau", self)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.dismiss_btn)
        self.hide()
