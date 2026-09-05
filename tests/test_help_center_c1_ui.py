import sys
import unittest

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from ui.help.shortcut_provider import RuntimeShortcutProvider


class TestHelpCenterC1RuntimeShortcutProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_tc177_reads_current_shortcuts_and_reflects_key_changes(self):
        window = QWidget()
        shortcut = QShortcut(QKeySequence("Ctrl+S"), window)
        provider = RuntimeShortcutProvider(window)
        provider.register_shortcut(shortcut, "save", "Save", "Global")

        self.assertEqual(provider.get_shortcuts()[0].sequence, "Ctrl+S")
        shortcut.setKey(QKeySequence("Ctrl+Shift+S"))
        self.app.processEvents()
        self.assertEqual(provider.get_shortcuts()[0].sequence, "Ctrl+Shift+S")
        window.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
