import pytest
from ui.SubEditor import time_str_to_ms
from core.export.subtitle_parser import _to_ms, parse_srt_content


def test_time_str_to_ms_supports_srt_standard():
    assert time_str_to_ms("00:00:01,500") == 1500
    assert time_str_to_ms("01:02:03,456") == 3723456


def test_time_str_to_ms_supports_vtt_dot_and_short_formats():
    assert time_str_to_ms("00:00:01.500") == 1500
    assert time_str_to_ms("01:23.456") == 83456
    assert time_str_to_ms("0:00:01,000") == 1000
    assert time_str_to_ms("00:00:01.5") == 1500


def test_time_str_to_ms_invalid_formats_return_negative_one():
    assert time_str_to_ms("invalid") == -1
    assert time_str_to_ms("00:60:00,000") == -1
    assert time_str_to_ms("00:00:60,000") == -1
    assert time_str_to_ms("") == -1


def test_subtitle_parser_to_ms_supports_dot_and_unpadded_hours():
    assert _to_ms("00:00:01,500") == 1500
    assert _to_ms("00:00:01.500") == 1500
    assert _to_ms("0:00:01,000") == 1000
    assert _to_ms("01:23.456") == 83456


def test_parse_srt_content_with_vtt_timestamps():
    content = "1\n00:00:01.000 --> 00:00:02.500\nHello VTT world\n"
    segs = parse_srt_content(content)
    assert len(segs) == 1
    assert segs[0]["start"] == 1000
    assert segs[0]["end"] == 2500
    assert segs[0]["text"] == "Hello VTT world"
