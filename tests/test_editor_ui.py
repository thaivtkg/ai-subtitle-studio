import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.SubEditor import SubtitleEditorWidget
except (ImportError, ModuleNotFoundError):
    QApplication = None
    SubtitleEditorWidget = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestSubtitleEditorUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.editor = SubtitleEditorWidget()
        self.editor.all_segments = [
            {"stt": "1", "start": "00:00:01,000", "end": "00:00:02,500", "text": "Câu 1"},
            {"stt": "2", "start": "00:00:03,000", "end": "00:00:04,500", "text": "Câu 2"},
        ]
        self.editor.render_page()

    def test_select_row_syncs_current_editor(self):
        self.editor.select_segment(1)
        self.assertEqual(self.editor.current_editor.text_edit.toPlainText(), "Câu 2")

    def test_playback_highlight_is_pagination_safe(self):
        self.editor.sync_playback_highlight(0)
        self.assertEqual(self.editor.current_index, 0)
        self.assertEqual(self.editor.table.currentRow(), 0)

    def test_invalid_timing_is_rejected(self):
        self.editor.select_segment(0)
        self.editor.current_editor.start_edit.setText("00:00:03,000")
        self.editor._apply_current_editor({
            "start": "00:00:03,000",
            "end": "00:00:02,500",
            "text": "Câu 1",
        })
        self.assertEqual(self.editor.all_segments[0]["start"], "00:00:01,000")

    def tearDown(self):
        self.editor.deleteLater()
