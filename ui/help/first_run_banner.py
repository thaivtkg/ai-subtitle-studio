from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class FirstRunBanner(QWidget):
    """Non-blocking first-run invitation banner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("first_run_banner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#first_run_banner { background-color: #e3f2fd; "
            "border: 1px solid #90caf9; border-radius: 4px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(QLabel("Chào mừng bạn! Khám phá hướng dẫn sử dụng nhanh.", self))
        layout.addStretch()
        self.start_btn = QPushButton("Bắt đầu hướng dẫn", self)
        self.dismiss_btn = QPushButton("Để sau", self)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.dismiss_btn)
