import unittest

from core.subtitle_editing.subtitle_time_range_filter import (
    TimeRangeValidationError,
    indices_for_time_range,
    parse_minute_range,
)


class MinuteRangeParserTests(unittest.TestCase):
    def test_blank_both_disables_filter(self):
        self.assertIsNone(parse_minute_range("", ""))

    def test_integer_minutes_to_ms(self):
        r = parse_minute_range("1", "5")
        self.assertEqual((r.start_ms, r.end_ms), (60_000, 300_000))

    def test_decimal_dot_and_comma(self):
        self.assertEqual(parse_minute_range("1.5", "2.25").start_ms, 90_000)
        self.assertEqual(parse_minute_range("1,5", "2,25").end_ms, 135_000)

    def test_missing_second_input_rejected(self):
        with self.assertRaises(TimeRangeValidationError):
            parse_minute_range("1", "")

    def test_non_numeric_rejected(self):
        for value in ("abc", "-1", "1:30", "1.2.3", "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(TimeRangeValidationError):
                parse_minute_range(value, "5")

    def test_end_must_be_greater(self):
        for start, end in (("2", "2"), ("5", "1"), ("1.000001", "1.000002")):
            with self.subTest(start=start, end=end), self.assertRaises(TimeRangeValidationError):
                parse_minute_range(start, end)

    def test_duration_bound(self):
        with self.assertRaisesRegex(TimeRangeValidationError, "vượt thời lượng video"):
            parse_minute_range("1", "3", max_duration_ms=120_000)

    def test_intersects_boundary_and_keeps_crossing_segments(self):
        segments = [
            {"id": "before", "start": "00:00:30,000", "end": "00:00:59,999"},
            {"id": "cross_start", "start": "00:00:50,000", "end": "00:01:10,000"},
            {"id": "inside", "start": "00:01:30,000", "end": "00:02:00,000"},
            {"id": "cross_end", "start": "00:04:50,000", "end": "00:05:10,000"},
            {"id": "after", "start": "00:05:00,000", "end": "00:05:30,000"},
        ]
        r = parse_minute_range("1", "5")
        self.assertEqual(indices_for_time_range(segments, r), [1, 2, 3])
        self.assertEqual([s["id"] for s in segments], ["before", "cross_start", "inside", "cross_end", "after"])

    def test_no_filter_returns_all_indices(self):
        self.assertEqual(indices_for_time_range([{}, {}, {}], None), [0, 1, 2])

    def test_invalid_timing_can_still_be_found_by_start(self):
        segments = [{"start": "00:02:00,000", "end": "00:01:00,000"}]
        self.assertEqual(indices_for_time_range(segments, (60_000, 180_000)), [0])


if __name__ == "__main__":
    unittest.main()
