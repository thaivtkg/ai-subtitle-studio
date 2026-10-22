import os
import pytest
from PySide6.QtWidgets import QApplication
from unittest.mock import MagicMock


def test_ac_srt_01_srt_parser_loads_file(tmp_path):
    """AC-SRT-01: Module core.srt_parser tồn tại và nạp file SRT thành công không văng ModuleNotFoundError"""
    from core.srt_parser import SrtParser

    srt_file = tmp_path / "sample.srt"
    srt_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello Senpai!\n\n2\n00:00:04,000 --> 00:00:06,000\nMagical Girl\n",
        encoding="utf-8",
    )

    segments = SrtParser.parse(str(srt_file))
    assert len(segments) == 2
    assert segments[0]["start"] == 1000
    assert segments[0]["end"] == 3500
    assert segments[0]["text"] == "Hello Senpai!"
    assert segments[1]["start"] == 4000
    assert segments[1]["end"] == 6000
    assert segments[1]["text"] == "Magical Girl"


def test_srt_parser_handles_non_utf8_fallback(tmp_path):
    """SrtParser không bị crash khi gặp file có ký tự byte lạ (dùng errors='replace')"""
    from core.srt_parser import SrtParser

    srt_file = tmp_path / "corrupted.srt"
    # Ghi byte không hợp lệ trong UTF-8
    srt_file.write_bytes(
        b"1\r\n00:00:01,000 --> 00:00:03,000\r\nHello \xff\xfe world\r\n\r\n"
    )

    segments = SrtParser.parse(str(srt_file))
    assert len(segments) == 1
    assert segments[0]["start"] == 1000
    assert "Hello" in segments[0]["text"]


def test_ac_zoom_01_and_02_zoom_buttons_ui(qapp):
    """AC-ZOOM-01 & 02: Nút zoom trên Timeline hiển thị dấu − và +, không tàng hình và zoom hoạt động"""
    from ui.Gui import MainWindow

    win = MainWindow()
    assert hasattr(win, "btn_zoom_out")
    assert hasattr(win, "btn_zoom_in")

    # Ký tự toán học chuẩn, không dùng emoji 🔍
    assert win.btn_zoom_out.text() in ("−", "-")
    assert win.btn_zoom_in.text() == "+"

    # Kích thước tối ưu không bị elide
    assert win.btn_zoom_out.width() >= 28
    assert win.btn_zoom_in.width() >= 28

    init_zoom = win.timeline_widget.pixels_per_second

    # Bấm zoom in
    win.btn_zoom_in.click()
    assert win.timeline_widget.pixels_per_second > init_zoom

    # Bấm zoom out 2 lần
    win.btn_zoom_out.click()
    win.btn_zoom_out.click()
    assert win.timeline_widget.pixels_per_second < init_zoom

    win.close()
