import pytest
from core.subtitle_quality.style_preset_resolver import StylePresetResolver


def test_resolve_normal():
    global_s = {"font_name": "Arial", "font_size": 20, "outline_width": 2.0}
    s = StylePresetResolver.resolve_style("normal", global_s)
    assert s["font_name"] == "Arial"
    assert s["font_size"] == 20
    assert s["font_color"] == "#FFFFFF"
    assert s["outline_width"] == 2.0
    assert not s.get("bold")
    assert not s.get("italic")


def test_resolve_loud():
    global_s = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2.0}
    s = StylePresetResolver.resolve_style("loud", global_s)
    assert s["font_name"] == "Segoe UI"
    assert s["font_size"] == 24
    assert s["font_color"] == "#FFE600"
    assert s["outline_width"] == 3.5
    assert s.get("bold") is True
    assert not s.get("italic")


def test_resolve_whisper():
    global_s = {"font_name": "Segoe UI", "font_size": 20, "outline_width": 2.0}
    s = StylePresetResolver.resolve_style("whisper", global_s)
    assert s["font_name"] == "Segoe UI"
    assert s["font_size"] == 17
    assert s["font_color"] == "#D0D0D0"
    assert s["outline_width"] == 1.5
    assert s.get("italic") is True
    assert not s.get("bold")


def test_resolve_fallback_unknown_preset():
    global_s = {"font_name": "Roboto", "font_size": 30}
    s = StylePresetResolver.resolve_style("unknown", global_s)
    assert s["font_size"] == 30
    assert s["font_color"] == "#FFFFFF"
    assert not s.get("bold")
    assert not s.get("italic")


def test_resolve_preserves_other_global_style_attributes():
    global_s = {
        "font_name": "Segoe UI",
        "font_size": 20,
        "outline_color": "#000000",
        "shadow_offset": 2,
    }
    s = StylePresetResolver.resolve_style("loud", global_s)
    assert s["outline_color"] == "#000000"
    assert s["shadow_offset"] == 2
