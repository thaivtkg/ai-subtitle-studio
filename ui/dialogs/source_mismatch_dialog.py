from enum import Enum

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class SourceMismatchChoice(Enum):
    RESTORE_UNLINKED = "restore_unlinked"
    DISCARD = "discard"


class SourceMismatchDialog(QDialog):
    choices = (SourceMismatchChoice.RESTORE_UNLINKED, SourceMismatchChoice.DISCARD)

    def __init__(self, session_id: str, project: str, timestamp: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Source mismatch")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Project: {project}\nSession: {session_id}\nSaved: {timestamp}"))
        restore = QPushButton("Restore unlinked")
        discard = QPushButton("Discard")
        restore.clicked.connect(lambda: self.done(1))
        discard.clicked.connect(lambda: self.done(0))
        layout.addWidget(restore)
        layout.addWidget(discard)
