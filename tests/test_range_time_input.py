import unittest

from core.subtitle_generation.range_time_input import (
    RangeInputError,
    format_range_value_ms,
    parse_range_value_ms,
)


class RangeTimeInputTests(unittest.TestCase):
    def test_seconds_accepts_dot_and_comma(self):
        self.assertEqual(parse_range_value_ms("60.5", "seconds"), 60_500)
        self.assertEqual(parse_range_value_ms("60,5", "seconds"), 60_500)

    def test_minutes_accepts_dot_and_comma(self):
        self.assertEqual(parse_range_value_ms("1.5", "minutes"), 90_000)
        self.assertEqual(parse_range_value_ms("1,5", "minutes"), 90_000)

    def test_integer_and_zero(self):
        self.assertEqual(parse_range_value_ms("70", "seconds"), 70_000)
        self.assertEqual(parse_range_value_ms("0", "minutes"), 0)

    def test_rejects_empty_input(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("", "seconds")

    def test_rejects_negative_input(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("-1", "minutes")

    def test_rejects_text(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("one", "seconds")

    def test_rejects_unit_suffix_because_unit_is_explicit(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("60s", "seconds")

    def test_rejects_scientific_notation(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("1e3", "seconds")

    def test_rejects_multiple_decimal_separators(self):
        with self.assertRaises(RangeInputError):
            parse_range_value_ms("1,2.3", "minutes")

    def test_rounds_to_nearest_millisecond(self):
        self.assertEqual(parse_range_value_ms("0.0005", "seconds"), 1)

    def test_format_seconds(self):
        self.assertEqual(format_range_value_ms(60_500, "seconds"), "60.5")

    def test_format_minutes(self):
        self.assertEqual(format_range_value_ms(90_000, "minutes"), "1.5")

    def test_unit_conversion_format_is_compact_and_millisecond_safe(self):
        shown = format_range_value_ms(60_500, "minutes")
        self.assertEqual(shown, "1.008333")
        self.assertEqual(parse_range_value_ms(shown, "minutes"), 60_500)


if __name__ == "__main__":
    unittest.main()
