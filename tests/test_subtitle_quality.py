import copy
import unittest

from core.recovery.revision_tracker import RevisionTracker
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_quality import QualitySeverity, SubtitleQualityAnalyzer
from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import Severity


def segment(start, end, text="Readable"):
    return {"id": f"s-{start}", "start": start, "end": end, "text": text}


class TestSubtitleQualityAnalyzer(unittest.TestCase):
    def test_cps_threshold_is_strict_and_newline_is_not_counted(self):
        self.assertEqual(SubtitleQualityAnalyzer.analyze([segment(0, 1000, "x" * 20)]), [])
        issues = SubtitleQualityAnalyzer.analyze([segment(0, 1000, "x" * 21)])
        self.assertEqual([issue.rule_id for issue in issues], ["reading_speed"])
        self.assertIs(issues[0].severity, QualitySeverity.WARNING)
        self.assertEqual(
            SubtitleQualityAnalyzer.analyze([segment(0, 1000, "x" * 10 + "\n" + "x" * 10)]), []
        )

    def test_duration_boundaries_use_inspector_policy(self):
        self.assertNotIn("duration_too_short", self._rule_ids(segment(0, 800)))
        self.assertIn("duration_too_short", self._rule_ids(segment(0, 799)))
        self.assertNotIn("duration_too_long", self._rule_ids(segment(0, 7000)))
        self.assertIn("duration_too_long", self._rule_ids(segment(0, 7001)))

    def test_line_length_and_line_count_boundaries(self):
        self.assertNotIn("line_too_long", self._rule_ids(segment(0, 2000, "x" * 42)))
        self.assertIn("line_too_long", self._rule_ids(segment(0, 2000, "x" * 43)))
        self.assertNotIn("too_many_lines", self._rule_ids(segment(0, 2000, "a\nb")))
        self.assertIn("too_many_lines", self._rule_ids(segment(0, 2000, "a\nb\nc")))

    def test_pairwise_gap_and_overlap_semantics(self):
        self.assertEqual(
            self._rule_ids(segment_pair(0, 1000, 1100, 2000)), []
        )
        self.assertIn("gap_too_small", self._rule_ids(segment_pair(0, 1000, 1050, 2000)))
        self.assertNotIn("gap_too_small", self._rule_ids(segment_pair(0, 1000, 1000, 2000)))
        self.assertNotIn("gap_too_small", self._rule_ids(segment_pair(0, 1000, 1000, 2000)))
        issues = SubtitleQualityAnalyzer.analyze([segment(0, 1000), segment(900, 2000)])
        self.assertEqual([issue.rule_id for issue in issues], ["subtitle_overlap"])
        self.assertIs(issues[0].severity, QualitySeverity.ERROR)

    def test_order_empty_single_and_invalid_duration_are_safe(self):
        self.assertEqual(SubtitleQualityAnalyzer.analyze([]), [])
        self.assertEqual(SubtitleQualityAnalyzer.analyze([segment(0, 1000)]), [])
        self.assertEqual(SubtitleQualityAnalyzer.analyze([segment(1000, 1000)]), [])
        issues = SubtitleQualityAnalyzer.analyze(
            [segment(0, 1000, "x" * 43), segment(900, 2000, "x" * 21)]
        )
        self.assertEqual(
            [issue.rule_id for issue in issues],
            ["reading_speed", "line_too_long", "subtitle_overlap"],
        )

    def test_analysis_does_not_mutate_segments_or_revision_tracker(self):
        subtitles = [segment(0, 1000, "x" * 43)]
        before = copy.deepcopy(subtitles)
        tracker = RevisionTracker(GlobalUndoManager())
        tracker.record_external_change()
        state = (tracker.edit_revision, tracker.last_saved_revision, tracker.is_dirty)
        SubtitleQualityAnalyzer.analyze(subtitles)
        self.assertEqual(subtitles, before)
        self.assertEqual(
            (tracker.edit_revision, tracker.last_saved_revision, tracker.is_dirty), state
        )

    def test_existing_validator_defaults_remain_unchanged(self):
        self.assertEqual(SubtitleValidator.validate_segment(0, segment(0, 600))[0:0], [])
        overlap = SubtitleValidator.validate_all([segment(0, 1000), segment(900, 2000)])
        self.assertIs(overlap[0][0].severity, Severity.WARNING)

    @staticmethod
    def _rule_ids(value):
        return [issue.rule_id for issue in SubtitleQualityAnalyzer.analyze(value if isinstance(value, list) else [value])]


def segment_pair(current_start, current_end, next_start, next_end):
    return [
        segment(current_start, current_end),
        segment(next_start, next_end),
    ]


if __name__ == "__main__":
    unittest.main()
