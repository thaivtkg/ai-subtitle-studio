import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.quality_inspector_panel import QualityInspectorPanel
except (ImportError, ModuleNotFoundError):
    QApplication = None
    QualityInspectorPanel = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestQualityInspectorPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_shows_summary_and_all_issues(self):
        panel = QualityInspectorPanel()
        panel.set_segments([
            {"id": "one", "start": 0, "end": 400, "text": "x" * 20},
            {"id": "two", "start": 350, "end": 1000, "text": "ok"},
        ])
        panel.refresh()
        self.assertEqual(panel.issue_list.count(), 4)
        self.assertIn("Error", panel.summary_label.text())
        self.assertIn("Warning", panel.summary_label.text())

    def test_severity_filter_and_jump_use_issue_index(self):
        panel = QualityInspectorPanel()
        jumped = []
        panel.jump_requested.connect(jumped.append)
        panel.set_segments([
            {"id": "one", "start": 0, "end": 400, "text": "x" * 20},
            {"id": "two", "start": 350, "end": 1000, "text": "ok"},
        ])
        panel.refresh()
        panel.filter_combo.setCurrentText("Errors")
        self.assertEqual(panel.issue_list.count(), 1)
        panel.issue_list.setCurrentRow(0)
        panel.jump_button.click()
        self.assertEqual(jumped, [0])

    def test_refresh_replaces_snapshot_results(self):
        panel = QualityInspectorPanel()
        segments = [{"id": "one", "start": 0, "end": 2000, "text": "ok"}]
        panel.set_segments(segments)
        panel.refresh()
        self.assertEqual(panel.issue_list.count(), 0)
        segments[0]["text"] = "x" * 43
        panel.set_segments(segments)
        panel.refresh()
        self.assertEqual(panel.issue_list.count(), 2)


if __name__ == "__main__":
    unittest.main()
