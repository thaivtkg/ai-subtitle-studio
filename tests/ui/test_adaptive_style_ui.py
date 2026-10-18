import pytest
from PySide6.QtGui import QColor
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.commands.edit_style_command import EditStyleCommand
from ui.SubEditor import SubtitleEditorWidget


def test_edit_style_command_undo_redo():
    undo_mgr = GlobalUndoManager()
    segs = [{"id": "s1", "style_preset": "normal"}]
    cmd = EditStyleCommand([{"index": 0, "old_preset": "normal", "new_preset": "loud"}], segs)
    undo_mgr.push(cmd)
    assert segs[0]["style_preset"] == "loud"
    undo_mgr.undo()
    assert segs[0]["style_preset"] == "normal"
    undo_mgr.redo()
    assert segs[0]["style_preset"] == "loud"


def test_stt_badge_rendering(qapp):
    editor = SubtitleEditorWidget()
    editor.all_segments = [
        {"stt": "1", "start": "00:00:01,000", "end": "00:00:03,000", "text": "A", "style_preset": "loud"},
        {"stt": "2", "start": "00:00:04,000", "end": "00:00:06,000", "text": "B", "style_preset": "whisper"},
        {"stt": "3", "start": "00:00:07,000", "end": "00:00:09,000", "text": "C", "style_preset": "normal"},
    ]
    editor.render_page()
    item_0 = editor.table.item(0, 0)
    item_1 = editor.table.item(1, 0)
    item_2 = editor.table.item(2, 0)

    assert "⚡" in item_0.text()
    assert item_0.background().color() == QColor(255, 230, 0, 18)
    assert "🤫" in item_1.text()
    assert "⚡" not in item_2.text()
    assert "🤫" not in item_2.text()
