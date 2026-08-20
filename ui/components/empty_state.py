from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ui.theme import Theme


class EmptyStateWidget(QWidget):
    action_clicked = Signal()

    def __init__(self, icon="📁", title="No Data", description="Không có dữ liệu hiển thị.", action_text=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setStyleSheet("font-size: 40px; border: none; background: transparent;")
        self.lbl_icon.setAlignment(Qt.AlignCenter)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Theme.TEXT_PRIMARY}; border: none; background: transparent;")
        self.lbl_title.setAlignment(Qt.AlignCenter)

        self.lbl_desc = QLabel(description)
        self.lbl_desc.setStyleSheet(f"font-size: 12px; color: {Theme.TEXT_MUTED}; border: none; background: transparent;")
        self.lbl_desc.setAlignment(Qt.AlignCenter)
        self.lbl_desc.setWordWrap(True)

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_desc)

        if action_text:
            self.btn_action = QPushButton(action_text)
            self.btn_action.setObjectName("btn_secondary")
            self.btn_action.setCursor(Qt.PointingHandCursor)
            self.btn_action.setFixedHeight(32)
            self.btn_action.clicked.connect(self.action_clicked.emit)
            layout.addWidget(self.btn_action, alignment=Qt.AlignCenter)