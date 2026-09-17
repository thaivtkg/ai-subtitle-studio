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


def lifecycle_fixture():
    return [
        {"id": "one", "start": 1000, "end": 3000, "text": "normal"},
        {"id": "two", "start": 4000, "end": 4900, "text": "x" * 43},
        {"id": "three", "start": 6000, "end": 6600, "text": "short"},
        {"id": "four", "start": 8000, "end": 16000, "text": "long"},
        {"id": "five", "start": 17000, "end": 20000, "text": "x" * 43},
        {"id": "six", "start": 21000, "end": 24000, "text": "a\nb\nc"},
        {"id": "seven", "start": 25000, "end": 27000, "text": "overlap"},
        {"id": "eight", "start": 26800, "end": 29000, "text": "overlap"},
        {"id": "nine", "start": 30000, "end": 32000, "text": "gap"},
        {"id": "ten", "start": 32050, "end": 34000, "text": "gap"},
    ]


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
        panel.set_segments([{"id": "old", "start": 0, "end": 3000, "text": "x" * 43}])
        panel.refresh()
        self.assertIn("line_too_long", panel.issue_list.item(0).text())

        panel.set_segments([{"id": "new", "start": 0, "end": 1000, "text": "x" * 21}])

        self.assertEqual(panel.issue_list.count(), 0)
        panel.refresh()
        self.assertEqual(panel.issue_list.count(), 1)
        self.assertIn("reading_speed", panel.issue_list.item(0).text())
        self.assertNotIn("line_too_long", panel.issue_list.item(0).text())

    def test_edit_marks_analysis_stale_without_false_clean_state(self):
        panel = QualityInspectorPanel()
        segments = lifecycle_fixture()
        panel.set_segments(segments)
        panel.refresh()
        self.assertIn("duration_too_short", [issue.rule_id for issue in panel._issues])

        edited = [dict(segment) for segment in segments]
        edited[2]["end"] = 6900
        mark_stale = getattr(panel, "mark_segments_stale", None)
        self.assertTrue(callable(mark_stale))
        mark_stale(edited)

        self.assertEqual(getattr(panel, "analysis_state", None), "STALE")
        self.assertEqual(panel.issue_list.count(), 0)
        self.assertNotIn("No quality issues found", panel.empty_state_label.text())
        self.assertIn("Refresh to reanalyze", panel.empty_state_label.text())
        self.assertFalse(panel.jump_button.isEnabled())

    def test_refresh_after_edit_keeps_unrelated_issues(self):
        panel = QualityInspectorPanel()
        segments = lifecycle_fixture()
        panel.set_segments(segments)
        panel.refresh()

        edited = [dict(segment) for segment in segments]
        edited[2]["end"] = 6900
        panel.mark_segments_stale(edited)
        panel.refresh()

        issue_keys = {(issue.subtitle_index, issue.rule_id) for issue in panel._issues}
        self.assertNotIn((2, "duration_too_short"), issue_keys)
        for expected in [
            (1, "reading_speed"),
            (1, "line_too_long"),
            (3, "duration_too_long"),
            (4, "line_too_long"),
            (5, "too_many_lines"),
            (6, "subtitle_overlap"),
            (8, "gap_too_small"),
        ]:
            self.assertIn(expected, issue_keys)
        self.assertEqual(getattr(panel, "analysis_state", None), "CURRENT")

    def test_edit_violation_returns_after_refresh(self):
        panel = QualityInspectorPanel()
        segments = lifecycle_fixture()
        panel.set_segments(segments)
        panel.refresh()

        edited = [dict(segment) for segment in segments]
        edited[2]["end"] = 6900
        panel.mark_segments_stale(edited)
        panel.refresh()
        self.assertNotIn(
            (2, "duration_too_short"),
            {(issue.subtitle_index, issue.rule_id) for issue in panel._issues},
        )

        edited[2]["end"] = 6500
        panel.mark_segments_stale(edited)
        self.assertEqual(panel.analysis_state, "STALE")
        panel.refresh()
        self.assertIn(
            (2, "duration_too_short"),
            {(issue.subtitle_index, issue.rule_id) for issue in panel._issues},
        )


if __name__ == "__main__":
    unittest.main()
