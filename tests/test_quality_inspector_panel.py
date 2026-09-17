import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.quality_inspector_panel import QualityInspectorPanel
    from ui.theme import Theme
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

    def test_issue_list_has_explicit_dark_readable_quality_theme(self):
        panel = QualityInspectorPanel()
        panel.set_segments([
            {"id": "error", "start": 0, "end": 1000, "text": "x" * 21},
            {"id": "warning", "start": 900, "end": 2000, "text": "ok"},
        ])
        panel.refresh()

        style = panel.issue_list.styleSheet()
        self.assertIn(f"background-color: {Theme.SURFACE}", style)
        self.assertIn(f"background-color: {Theme.SURFACE_SOFT}", style)
        self.assertIn(f"color: {Theme.TEXT_PRIMARY}", style)
        self.assertIn("QListWidget::item:selected", style)
        item_colors = {
            panel.issue_list.item(index).foreground().color().name().lower()
            for index in range(panel.issue_list.count())
        }
        self.assertIn(Theme.DANGER.lower(), item_colors)
        self.assertIn(Theme.WARNING.lower(), item_colors)

    def test_replacing_snapshot_clears_previous_results_and_disables_jump(self):
        panel = QualityInspectorPanel()
        panel.set_segments([{"id": "old", "start": 0, "end": 400, "text": "x" * 20}])
        panel.refresh()
        self.assertGreater(panel.issue_list.count(), 0)

        panel.set_segments([])
        panel.refresh()

        self.assertEqual(panel.issue_list.count(), 0)
        self.assertEqual(panel.summary_label.text(), "0 Errors · 0 Warnings · 0 Info")
        self.assertFalse(panel.jump_button.isEnabled())
        self.assertIn("No active subtitles to inspect", panel.empty_state_label.text())

    def test_source_switch_replaces_old_issue_set(self):
        panel = QualityInspectorPanel()
        panel.set_segments([{"id": "old", "start": 0, "end": 400, "text": "x" * 20}])
        panel.refresh()
        self.assertGreater(panel.issue_list.count(), 0)

        panel.set_segments([{"id": "new", "start": 0, "end": 2000, "text": "ok"}])

        self.assertEqual(panel.issue_list.count(), 0)
        panel.refresh()
        self.assertEqual(panel.issue_list.count(), 0)


if __name__ == "__main__":
    unittest.main()
