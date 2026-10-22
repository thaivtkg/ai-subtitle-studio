import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from ui.SubEditor import SubtitleEditorWidget
from ui.timeline.timeline_widget import TimelineWidget
from ui.timeline.waveform_view import WaveformView
from ui.timeline.subtitle_track import SubtitleTrack


def test_ac_ui_01_toolbar_buttons_text_and_compact(qapp):
    """AC-UI-01: Tên các nút hành động trên Toolbar được tinh gọn tránh tràn viền"""
    editor = SubtitleEditorWidget()
    assert "Quét Audio" in editor.reanalyze_audio_style_btn.text()
    assert "Chồng lấn" in editor.fix_overlap_btn.text()
    assert "Chốt Timing" in editor.approve_btn.text()
    assert "Lưu Draft" in editor.save_draft_btn.text()
    assert "Lưu SRT" in editor.save_btn.text()


def test_ac_ui_02_timeline_minimum_height(qapp):
    """AC-UI-02: TimelineWidget có chiều cao tối thiểu >= 185px và kích thước track được tối ưu"""
    waveform = WaveformView()
    assert waveform.height() <= 80  # Đã tối ưu từ 100px xuống 75px

    track = SubtitleTrack()
    assert track.height() <= 55  # Đã tối ưu từ 60px xuống 50px

    tl = TimelineWidget()
    # Khi tải xong hoặc gán min height, phải đảm bảo >= 185px để không nuốt gap_row
    assert tl.minimumHeight() >= 185 or tl.sizeHint().height() >= 185


def test_ac_ui_03_ai_drawer_button_in_topbar(qapp):
    """AC-UI-03: Có nút mở Bảng Điều Khiển AI trực quan trên Topbar"""
    from ui.Gui import MainWindow

    win = MainWindow()
    assert hasattr(win, "btn_ai_drawer")
    assert "Bảng Điều Khiển AI" in win.btn_ai_drawer.text()
    assert hasattr(win, "btn_maximize")
    win.close()
