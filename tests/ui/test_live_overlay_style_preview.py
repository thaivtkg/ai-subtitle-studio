import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from player.video_player import VideoPlayerWidget


@pytest.fixture
def player_widget(qapp):
    widget = VideoPlayerWidget()
    return widget


def test_tc_preview_01_loud_preset_styling_and_caching(player_widget):
    """TC-PREVIEW-01: Subtitle loud chuyển đổi font đậm, to và cache preset để tránh lag"""
    player = player_widget

    # Giả lập phân đoạn loud
    player.set_subtitle_text("HÉT LÊN!", style_preset="loud")

    assert player._last_style_preset == "loud"
    sheet = player.lbl_sub.styleSheet().lower()
    assert "bold" in sheet
    assert "24px" in sheet or "color" in sheet

    # Kiểm tra tối ưu không setStyleSheet lặp lại nếu cùng preset
    original_set_stylesheet = player.lbl_sub.setStyleSheet
    player.lbl_sub.setStyleSheet = MagicMock()

    player.set_subtitle_text("HÉT LẦN HAI!", style_preset="loud")
    player.lbl_sub.setStyleSheet.assert_not_called()
    player.lbl_sub.setStyleSheet = original_set_stylesheet


def test_tc_preview_02_whisper_preset_styling(player_widget):
    """TC-PREVIEW-02: Subtitle whisper chuyển sang font nghiêng, nhỏ hơn và màu dịu"""
    player = player_widget

    player.set_subtitle_text("thì thầm khẽ...", style_preset="whisper")

    assert player._last_style_preset == "whisper"
    sheet = player.lbl_sub.styleSheet().lower()
    assert "italic" in sheet


def test_tc_preview_normal_preset_reset(player_widget):
    """Khi quay về normal hoặc xóa sub, style preset được hoàn nguyên"""
    player = player_widget

    player.set_subtitle_text("Loud", style_preset="loud")
    assert player._last_style_preset == "loud"

    player.set_subtitle_text("Normal", style_preset="normal")
    assert player._last_style_preset == "normal"
    sheet = player.lbl_sub.styleSheet().lower()
    assert "bold" not in sheet
    assert "italic" not in sheet
