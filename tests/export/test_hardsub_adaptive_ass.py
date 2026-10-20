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


def test_format_ass_timestamp_supports_float_seconds():
    from core.Backend import _format_ass_timestamp
    assert _format_ass_timestamp(1.5) == "0:00:01.50"
    assert _format_ass_timestamp(72.35) == "0:01:12.35"
    assert _format_ass_timestamp("00:01:12,350") == "0:01:12.35"


def test_build_multistyle_ass_custom_font_color_and_fallback_for_named_color():
    segments = [
        {"start": 1.5, "end": 3.25, "text": "Testing float", "style_preset": "normal"}
    ]
    # Custom valid hex color #00FF88 -> ASS BGR &H0088FF00
    global_style = {"font_name": "Arial", "font_size": 20, "font_color": "#00FF88"}
    ass_text = _build_multistyle_ass(segments, 1280, 720, None, global_style)
    assert "Style: Style_Normal,Arial,20,&H0088FF00" in ass_text
    assert "Dialogue: 0,0:00:01.50,0:00:03.25,Style_Normal" in ass_text

    # Named color string like "yellow" (6 chars) should safely fall back to &H00FFFFFF
    global_style_named = {"font_name": "Arial", "font_size": 20, "font_color": "yellow"}
    ass_named = _build_multistyle_ass(segments, 1280, 720, None, global_style_named)
    assert "Style: Style_Normal,Arial,20,&H00FFFFFF" in ass_named


def test_burn_hardsub_with_normal_segments_generates_ass_file():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    from core.subtitle_placement import SubtitlePlacementState
    from core.Backend import burn_hardsub

    class _FakeStdout:
        def __iter__(self):
            return iter(())
        def close(self):
            return None

    class _FakeProcess:
        def __init__(self):
            self.stdout = _FakeStdout()
            self.returncode = 0
        def poll(self):
            return 0
        def wait(self):
            return 0

    with tempfile.TemporaryDirectory() as temp_dir:
        video = Path(temp_dir) / "video.mp4"
        srt = Path(temp_dir) / "sub.srt"
        output = Path(temp_dir) / "out.mp4"
        video.write_bytes(b"vid")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")

        segments = [{"start": "00:00:00,000", "end": "00:00:01,000", "text": "hi", "style_preset": "normal"}]
        with patch("core.runtime.runtime_paths.RuntimePaths.get_ffmpeg_exe", return_value="ffmpeg"), \
                patch("subprocess.Popen", return_value=_FakeProcess()) as mock_popen:
            burn_hardsub(
                str(video),
                str(srt),
                str(output),
                font_size=28,
                font_color="#00FF00",
                font_name="Arial",
                placement_state=SubtitlePlacementState(mode="bottom"),
                segments=segments,
                video_resolution=(1280, 720)
            )

        cmd = mock_popen.call_args.args[0]
        vf = cmd[cmd.index("-vf") + 1]
        assert ".ass" in vf


