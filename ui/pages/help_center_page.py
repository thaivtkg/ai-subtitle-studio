from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget


class HelpCenterPage(QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search help...")
        self._cards = QListWidget(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(175)
        self._search.textChanged.connect(self._schedule_search)
        self._timer.timeout.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Help Center", self))
        layout.addWidget(self._search)
        layout.addWidget(self._cards)
        self.refresh()

    def _schedule_search(self):
        self._timer.start()

    def refresh(self):
        cards = self._controller.search(self._search.text()) if self._controller else ()
        self._cards.clear()
        for card in cards:
            self._cards.addItem(
                f"{card.title} — {card.start.status_label} ({card.start.action_label})"
            )
