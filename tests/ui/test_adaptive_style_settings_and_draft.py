import os
import tempfile
import pytest
from ui.pages.settings_page import SettingsCenterPage
from core.services.project_service import ProjectService


def test_settings_has_adaptive_style_checkbox(qapp):
    page = SettingsCenterPage()
    assert hasattr(page, "chk_auto_audio_style")
    assert not page.chk_auto_audio_style.isChecked()  # default off


def test_draft_preserves_style_preset():
    service = ProjectService()
    segs = [{"id": "s1", "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hi", "style_preset": "loud"}]
    with tempfile.NamedTemporaryFile(suffix=".ai-subtitle-draft", delete=False) as f:
        tmp_path = f.name
    try:
        service.save_draft(tmp_path, segs)
        loaded = service.load_draft(tmp_path)
        assert loaded["segments"][0]["style_preset"] == "loud"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
