import unittest
from unittest.mock import MagicMock

# We use a mock application to avoid PySide6 init errors
from PySide6.QtWidgets import QApplication
import sys

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui.Gui import MainWindow
from core.database.tm_manager import TranslationMemoryManager

class TestTMSignals(unittest.TestCase):
    def setUp(self):
        self.mock_gui = MagicMock()
        self.mock_gui.tm_manager = TranslationMemoryManager(db_path=":memory:")

    def test_on_commit_segment_valid(self):
        MainWindow._on_commit_segment(self.mock_gui, "Hello", "Xin chào", "", "")
        
        matches = self.mock_gui.tm_manager.find_matches("Hello")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].target_text, "Xin chào")

    def test_on_commit_segment_unknown_source(self):
        MainWindow._on_commit_segment(self.mock_gui, "[Unknown Source]", "Bản dịch", "", "")
        
        matches = self.mock_gui.tm_manager.find_matches("[Unknown Source]")
        self.assertEqual(len(matches), 0)
        
        c = self.mock_gui.tm_manager.conn.cursor()
        c.execute("SELECT COUNT(*) FROM tm_segments")
        count = c.fetchone()[0]
        self.assertEqual(count, 0)

    def test_on_commit_segment_empty_source(self):
        MainWindow._on_commit_segment(self.mock_gui, "", "Bản dịch", "", "")
        
        c = self.mock_gui.tm_manager.conn.cursor()
        c.execute("SELECT COUNT(*) FROM tm_segments")
        count = c.fetchone()[0]
        self.assertEqual(count, 0)

if __name__ == "__main__":
    unittest.main()
