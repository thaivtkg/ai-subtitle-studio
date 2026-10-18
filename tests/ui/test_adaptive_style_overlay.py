import pytest
from PySide6.QtGui import QColor
from player.subtitle_overlay import SubtitleOverlay
from ui.animations.animation_types import SubtitleRenderInput


def test_overlay_renders_with_resolved_segment_style(qapp):
    overlay = SubtitleOverlay()
    overlay.font_family = "Segoe UI"
    overlay.font_size = 20

    render_input = SubtitleRenderInput(
        segment_id=1,
        start_ms=0,
        end_ms=2000,
        text="LOUD TEXT",
        style_preset="loud",
    )
    overlay.update_subtitle(render_input, 500)

    resolved = overlay.get_active_resolved_style()
    assert resolved["font_size"] == 24
    assert resolved["font_color"] == "#FFE600"
    assert resolved["outline_width"] == 3.5
    assert resolved["bold"] is True


def test_overlay_renders_with_whisper_preset(qapp):
    overlay = SubtitleOverlay()
    overlay.font_family = "Segoe UI"
    overlay.font_size = 20

    render_input = SubtitleRenderInput(
        segment_id=2,
        start_ms=0,
        end_ms=2000,
        text="whisper text",
        style_preset="whisper",
    )
    overlay.update_subtitle(render_input, 500)

    resolved = overlay.get_active_resolved_style()
    assert resolved["font_size"] == 17
    assert resolved["font_color"] == "#D0D0D0"
    assert resolved["outline_width"] == 1.5
    assert resolved["italic"] is True


def test_overlay_renders_normal_preset_by_default(qapp):
    overlay = SubtitleOverlay()
    overlay.font_family = "Segoe UI"
    overlay.font_size = 20

    render_input = SubtitleRenderInput(
        segment_id=3,
        start_ms=0,
        end_ms=2000,
        text="normal text",
    )
    overlay.update_subtitle(render_input, 500)

    resolved = overlay.get_active_resolved_style()
    assert resolved["font_size"] == 20
    assert resolved["font_color"].upper() == "#FFFFFF"
    assert not resolved.get("bold")
    assert not resolved.get("italic")
