import pytest
from core.Backend import _build_multistyle_ass
from core.subtitle_placement import SubtitlePlacementState


def test_build_multistyle_ass_contains_all_three_styles():
    segments = [
        {"start": "00:00:01,000", "end": "00:00:03,000", "text": "Hello", "style_preset": "normal"},
        {"start": "00:00:04,000", "end": "00:00:06,000", "text": "SHOUT!", "style_preset": "loud"},
        {"start": "00:00:07,000", "end": "00:00:09,000", "text": "psst...", "style_preset": "whisper"},
    ]
    global_style = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2}
    placement = SubtitlePlacementState(mode="bottom", x=50.0, y=85.0)

    ass_text = _build_multistyle_ass(segments, 1920, 1080, placement, global_style)

    # Check Styles defined with correct ASS BGR colors and flags
    assert "Style: Style_Normal,Segoe UI,20,&H00FFFFFF" in ass_text
    assert "Style: Style_Loud,Segoe UI,24,&H0000E6FF" in ass_text  # ASS BGR for #FFE600
    assert "Style: Style_Whisper,Segoe UI,17,&H00D0D0D0" in ass_text
    # Check Dialogues use corresponding style names
    assert "Dialogue: 0,0:00:01.00,0:00:03.00,Style_Normal" in ass_text
    assert "Dialogue: 0,0:00:04.00,0:00:06.00,Style_Loud" in ass_text
    assert "Dialogue: 0,0:00:07.00,0:00:09.00,Style_Whisper" in ass_text


def test_build_multistyle_ass_with_int_ms():
    segments = [
        {"start_ms": 1500, "end_ms": 3200, "text": "Testing ms", "style_preset": "loud"}
    ]
    global_style = {"font_name": "Arial", "font_size": 30}
    placement = SubtitlePlacementState(mode="bottom", x=50.0, y=90.0)

    ass_text = _build_multistyle_ass(segments, 1280, 720, placement, global_style)
    assert "Dialogue: 0,0:00:01.50,0:00:03.20,Style_Loud" in ass_text
