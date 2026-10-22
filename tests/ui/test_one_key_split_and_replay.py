import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QWidget
from unittest.mock import MagicMock

from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from ui.SubEditor import SubtitleEditorWidget


@pytest.fixture
def sub_editor_setup(qapp):
    widget = SubtitleEditorWidget()
    undo_mgr = GlobalUndoManager()
    widget.undo_manager = undo_mgr
    widget.all_segments = [
        {
            "id": "seg_1",
            "stt": "1",
            "start": "00:00:01,000",
            "end": "00:00:05,000",
            "text": "Hello magical world",
            "style_preset": "normal",
        }
    ]
    widget.current_index = 0
    return widget, undo_mgr


def test_tc_shortcut_01_split_at_playhead_success(sub_editor_setup):
    """TC-SHORTCUT-01: Bấm phím X khi playhead nằm giữa phân đoạn (>= 200ms)"""
    widget, undo_mgr = sub_editor_setup
    playhead_ms = 2500  # Cách start 1500ms, cách end 2500ms >= 200ms

    widget.trigger_split(playhead_ms)

    assert len(widget.all_segments) == 2
    seg1, seg2 = widget.all_segments[0], widget.all_segments[1]
    assert seg1["start"] == "00:00:01,000"
    assert seg1["end"] == "00:00:02,500"
    assert seg2["start"] == "00:00:02,500"
    assert seg2["end"] == "00:00:05,000"
    assert seg2["style_preset"] == "normal"
    assert seg1["id"] != seg2["id"]
    # Focus tự động chuyển sang phân đoạn thứ 2
    assert widget.current_index == 1


def test_tc_shortcut_03_split_near_edge_or_gap_ignored(sub_editor_setup):
    """TC-SHORTCUT-03: Bấm phím X khi sát mép (< 200ms) hoặc khoảng trống -> bỏ qua an toàn"""
    widget, undo_mgr = sub_editor_setup

    # Sát mép trái: 1100ms (cách 1000ms chỉ 100ms < 200ms)
    widget.trigger_split(1100)
    assert len(widget.all_segments) == 1

    # Sát mép phải: 4900ms (cách 5000ms chỉ 100ms < 200ms)
    widget.trigger_split(4900)
    assert len(widget.all_segments) == 1

    # Khoảng trống ngoài phân đoạn: 6000ms
    widget.trigger_split(6000)
    assert len(widget.all_segments) == 1


def test_tc_shortcut_02_focus_guard_typing(qapp):
    """TC-SHORTCUT-02: Bấm phím X khi đang focus trong ô soạn thảo -> không kích hoạt cắt"""
    from ui.Gui import MainWindow

    win = QWidget()
    text_edit = QTextEdit(win)
    win.show()
    text_edit.setFocus()
    qapp.processEvents()
    assert QApplication.focusWidget() == text_edit

    mock_main = MagicMock()
    mock_main.isActiveWindow.return_value = True

    ev_press_x = QKeyEvent(QEvent.KeyPress, Qt.Key_X, Qt.NoModifier, "x")
    consumed = MainWindow.eventFilter(mock_main, text_edit, ev_press_x)

    # Khi đang gõ chữ, eventFilter không được nuốt phím và không được gọi trigger_split_at_playhead
    assert consumed is not True
    mock_main.trigger_split_at_playhead.assert_not_called()
    win.close()


def test_tc_shortcut_04_replay_hotkey(qapp):
    """TC-SHORTCUT-04: Bấm phím R khi đang chọn phân đoạn -> replay đoạn đó"""
    from ui.Gui import MainWindow

    win = QWidget()
    win.show()
    win.setFocus()
    qapp.processEvents()

    mock_main = MagicMock()
    mock_main.isActiveWindow.return_value = True

    ev_press_r = QKeyEvent(QEvent.KeyPress, Qt.Key_R, Qt.NoModifier, "r")
    consumed = MainWindow.eventFilter(mock_main, win, ev_press_r)

    assert consumed is True
    mock_main.replay_focused_segment.assert_called_once()
    win.close()
