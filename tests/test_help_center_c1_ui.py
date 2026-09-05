import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from ui.help.shortcut_provider import RuntimeShortcutProvider
from ui.Gui import MainWindow
from ui.tutorial.navigation_adapter import MainWindowRouter, NavigationAdapter


class TestHelpCenterC1RuntimeShortcutProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_runtime_tour_uses_navigation_adapter_port(self):
        window = MainWindow(
            project_service=MagicMock(), media_import_service=MagicMock()
        )
        self.assertIsInstance(window.tour_router, MainWindowRouter)
        self.assertIsInstance(window.tour_navigation, NavigationAdapter)
        self.assertIs(window.tour_engine._navigation, window.tour_navigation)
        window.deleteLater()
        self.app.processEvents()

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
