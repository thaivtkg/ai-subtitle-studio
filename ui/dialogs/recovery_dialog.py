from enum import Enum

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class RecoveryChoice(Enum):
    RESTORE = "restore"
    DISCARD = "discard"


class RecoveryDialog(QDialog):
    choices = (RecoveryChoice.RESTORE, RecoveryChoice.DISCARD)

    def __init__(self, session_id: str, project: str, timestamp: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recovery available")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Project: {project}\nSession: {session_id}\nSaved: {timestamp}"))
        restore = QPushButton("Restore")
        discard = QPushButton("Discard")
        restore.clicked.connect(lambda: self.done(1))
        discard.clicked.connect(lambda: self.done(0))
        layout.addWidget(restore)
        layout.addWidget(discard)
