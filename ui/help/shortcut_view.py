from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget


class ShortcutView(QWidget):
    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._list = QListWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Keyboard Shortcuts", self))
        layout.addWidget(self._list)
        self.refresh()

    def refresh(self):
        self._list.clear()
        for name, sequence in self._provider.entries():
            self._list.addItem(f"{name}: {sequence}")
