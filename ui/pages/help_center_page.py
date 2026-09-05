from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.help.shortcut_view import ShortcutView


class HelpCenterPage(QWidget):
    start_guide_requested = Signal(str)

    def __init__(self, controller=None, shortcut_provider=None, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search help...")
        self._cards = QWidget(self)
        self._cards_layout = QVBoxLayout(self._cards)
        self._shortcuts = ShortcutView(shortcut_provider, self)
        self._notice = QLabel(self)
        self._notice.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(175)
        self._search.textChanged.connect(lambda _text: self._timer.start())
        self._timer.timeout.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Help Center", self))
        layout.addWidget(self._search)
        layout.addWidget(self._notice)
        layout.addWidget(self._cards)
        layout.addWidget(self._shortcuts)
        layout.addStretch()
        self.refresh()

    def _clear_cards(self):
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _add_card(self, card):
        row = QWidget(self._cards)
        row_layout = QVBoxLayout(row)
        row_layout.addWidget(QLabel(f"{card.title} — {card.badge}", row))
        row_layout.addWidget(QLabel(card.description, row))
        button = QPushButton(card.cta, row)
        button.setEnabled(card.enabled)
        button.clicked.connect(lambda _checked=False, guide_id=card.guide_id: self._start_guide(guide_id))
        row_layout.addWidget(button)
        self._cards_layout.addWidget(row)

    def _start_guide(self, guide_id):
        self.start_guide_requested.emit(guide_id)
        if self._controller is None:
            return
        result = self._controller.start_guide(guide_id)
        self._notice.setText(result.reason or result.status.value)
        self._notice.setVisible(result.status.value != "READY")

    def refresh(self):
        self._clear_cards()
        if self._controller is None:
            self._shortcuts.refresh()
            return
        cards = self._controller.build_guide_cards()
        query = self._search.text().strip()
        if query:
            results = self._controller.search(query)
            guide_ids = {item.item_id for item in results if item.result_type.value == "GUIDE"}
            cards = tuple(card for card in cards if card.guide_id in guide_ids)
        for card in cards:
            self._add_card(card)
        self._shortcuts.refresh()
