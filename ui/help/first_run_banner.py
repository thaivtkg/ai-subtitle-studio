from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class FirstRunBanner(QWidget):
    """C2 UI scaffold; behavior is intentionally not implemented yet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_btn = QPushButton("Bắt đầu hướng dẫn", self)
        self.dismiss_btn = QPushButton("Để sau", self)
        layout = QHBoxLayout(self)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.dismiss_btn)
