from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget


class ShortcutView(QWidget):
    def __init__(self, provider=None, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._list = QListWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Keyboard Shortcuts", self))
        layout.addWidget(self._list)
        self.refresh()

    def refresh(self):
        self._list.clear()
        if self._provider is None:
            return
        entries = self._provider.get_shortcuts() if hasattr(self._provider, "get_shortcuts") else self._provider.entries()
        for entry in entries:
            if isinstance(entry, tuple):
                name, sequence = entry
            else:
                name, sequence = entry.label, entry.sequence
            self._list.addItem(f"{name}: {sequence}")
