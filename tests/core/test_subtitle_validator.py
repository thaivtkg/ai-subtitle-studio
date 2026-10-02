import unittest

from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import Severity


class TestSubtitleValidator(unittest.TestCase):
    def test_valid_segment_has_no_issues(self):
        segment = {"start": 1000, "end": 3000, "text": "A readable line"}
        self.assertEqual(SubtitleValidator.validate_segment(0, segment), [])

    def test_structural_errors_are_reported(self):
        issues = SubtitleValidator.validate_segment(
            2, {"start": -1, "end": 500, "text": "Text"}, video_duration_ms=400
        )
        self.assertEqual({issue.code for issue in issues}, {"INVALID_START", "OUT_OF_VIDEO_RANGE"})
        self.assertTrue(all(issue.severity is Severity.ERROR for issue in issues))

    def test_quality_thresholds_are_reported(self):
        issues = SubtitleValidator.validate_segment(0, {"start": 0, "end": 400, "text": "x" * 20})
        self.assertEqual({issue.code for issue in issues}, {"HIGH_CPS", "TOO_SHORT"})
        self.assertTrue(all(issue.severity is Severity.WARNING for issue in issues))

    def test_empty_and_long_text_duration_are_reported(self):
        issues = SubtitleValidator.validate_segment(0, {"start": 0, "end": 8000, "text": " "})
        self.assertEqual({issue.code for issue in issues}, {"EMPTY_TEXT", "TOO_LONG"})

    def test_validate_all_reports_overlap_on_both_segments(self):
        segments = [
            {"start": 0, "end": 2000, "text": "One"},
            {"start": 1500, "end": 3000, "text": "Two"},
        ]
        issues = SubtitleValidator.validate_all(segments)
        self.assertEqual(issues[0][0].code, "OVERLAP")
        self.assertEqual(issues[1][0].code, "OVERLAP")
        self.assertIn("500ms", issues[0][0].message)

    def test_validator_accepts_srt_timestamp_values(self):
        segment = {"start": "00:00:01,000", "end": "00:00:03,000", "text": "Readable"}
        self.assertEqual(SubtitleValidator.validate_segment(0, segment), [])


if __name__ == "__main__":
    unittest.main()
