import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.subtitle_inspector_panel import SubtitleInspectorPanel
except (ImportError, ModuleNotFoundError):
    QApplication = None
    SubtitleInspectorPanel = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestSubtitleInspectorPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_emits_complete_default_style(self):
        panel = SubtitleInspectorPanel()
        received = []
        panel.style_changed.connect(received.append)
        panel.emit_current_style()
        self.assertEqual(received[-1]["font_size"], 40)
        self.assertEqual(received[-1]["font_color"], "#ffffff")
        self.assertEqual(received[-1]["outline_width"], 2)
        self.assertEqual(received[-1]["position"], "bottom")

    def test_preview_toggle_emits_boolean(self):
        panel = SubtitleInspectorPanel()
        received = []
        panel.preview_toggled.connect(received.append)
        panel.chk_preview.setChecked(False)
        self.assertEqual(received[-1], False)
