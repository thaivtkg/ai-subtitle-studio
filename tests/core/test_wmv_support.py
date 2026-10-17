import json
from unittest.mock import patch, MagicMock
import pytest
from core.media_import.url_classifier import URLClassifier, MediaURLType
from core.media_import.media_probe import MediaProbe
from ui.dialogs.new_project_dialog import NewProjectDialog
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

def test_url_classifier_recognizes_wmv():
    classifier = URLClassifier()
    assert classifier.classify("https://example.com/video.wmv") == MediaURLType.DIRECT_MEDIA
    assert classifier.is_obvious_direct_media("https://example.com/video.wmv") is True

def test_media_probe_wmv_extension(tmp_path):
    video_file = tmp_path / "test.wmv"
    video_file.write_bytes(b"dummy")
    probe = MediaProbe()
    fake_json = {
        "format": {"duration": "120.5", "format_name": "asf,wmv"},
        "streams": [{"codec_type": "video", "codec_name": "wmv2", "width": 1280, "height": 720}]
    }
    mock_res = MagicMock(returncode=0, stdout=json.dumps(fake_json), stderr="")
    with patch("subprocess.run", return_value=mock_res):
        result = probe.probe(video_file)
        assert result.extension == ".wmv"
        assert result.has_video is True
        assert result.duration == 120.5

def test_new_project_dialog_filter(qapp):
    with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=("video.wmv", "")) as mock_dialog:
        dialog = NewProjectDialog()
        dialog._browse_video()
        assert dialog.video_input.text() == "video.wmv"
        filter_str = mock_dialog.call_args[0][3]
        assert "*.wmv" in filter_str
