import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.commands.edit_timing_command import EditTimingCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from ui.SubEditor import SubtitleEditorWidget


app = QApplication.instance() or QApplication([])


class TestSubtitleCommands(unittest.TestCase):
    def setUp(self):
        self.data_provider = [
            {"start": 1000, "end": 3000, "text": "Câu gốc 1"},
            {"start": 4000, "end": 6000, "text": "Câu gốc 2"},
        ]
        self.undo_manager = GlobalUndoManager()

    def test_01_edit_text_command_undo_redo(self):
        cmd = EditTextCommand(0, self.data_provider[0]["text"], "Câu đã sửa", self.data_provider)
        self.undo_manager.push(cmd)
        self.assertEqual(self.data_provider[0]["text"], "Câu đã sửa")
        self.assertTrue(self.undo_manager.is_dirty)
        self.undo_manager.undo()
        self.assertEqual(self.data_provider[0]["text"], "Câu gốc 1")
        self.undo_manager.redo()
        self.assertEqual(self.data_provider[0]["text"], "Câu đã sửa")

    def test_02_edit_text_command_merge_typing(self):
        self.undo_manager.push(EditTextCommand(0, "Câu gốc 1", "Câu A", self.data_provider))
        self.undo_manager.push(EditTextCommand(0, "Câu A", "Câu AB", self.data_provider))
        self.undo_manager.push(EditTextCommand(0, "Câu AB", "Câu ABC", self.data_provider))
        self.assertEqual(self.data_provider[0]["text"], "Câu ABC")
        self.assertEqual(self.undo_manager.undo_stack.count(), 1)
        self.undo_manager.undo()
        self.assertEqual(self.data_provider[0]["text"], "Câu gốc 1")

    def test_03_edit_text_command_does_not_merge_across_segments(self):
        self.undo_manager.push(EditTextCommand(0, "Câu gốc 1", "Sửa 1", self.data_provider))
        self.undo_manager.push(EditTextCommand(1, "Câu gốc 2", "Sửa 2", self.data_provider))
        self.assertEqual(self.undo_manager.undo_stack.count(), 2)

    def test_04_edit_timing_command_undo_redo(self):
        cmd = EditTimingCommand(1, 4000, 6000, 4500, 7000, self.data_provider)
        self.undo_manager.push(cmd)
        self.assertEqual(self.data_provider[1]["start"], 4500)
        self.assertEqual(self.data_provider[1]["end"], 7000)
        self.undo_manager.undo()
        self.assertEqual(self.data_provider[1]["start"], 4000)
        self.assertEqual(self.data_provider[1]["end"], 6000)
        self.undo_manager.redo()
        self.assertEqual(self.data_provider[1]["start"], 4500)
        self.assertEqual(self.data_provider[1]["end"], 7000)


class TestEditorCommandIntegration(unittest.TestCase):
    def setUp(self):
        self.editor = SubtitleEditorWidget()
        self.undo_manager = GlobalUndoManager()
        self.editor.undo_manager = self.undo_manager
        self.undo_manager.state_changed.connect(self.editor.render_page)
        self.editor.all_segments = [
            {"start": 1000, "end": 3000, "text": "Hello World"},
            {"start": 4000, "end": 5000, "text": "Second Line"},
        ]
        self.editor.render_page()
        self.editor.show()

    def test_05_editor_text_change_pushes_command(self):
        self.editor.select_segment(0)
        self.editor.txt_content.setPlainText("Hello Universe")
        self.editor._apply_current_editor()
        self.assertEqual(self.editor.all_segments[0]["text"], "Hello Universe")
        self.assertEqual(self.editor.table.item(0, 4).text(), "Hello Universe")
        self.undo_manager.undo()
        self.assertEqual(self.editor.all_segments[0]["text"], "Hello World")
        self.assertEqual(self.editor.table.item(0, 4).text(), "Hello World")

    def test_06_editor_timing_change_pushes_command(self):
        self.editor.select_segment(0)
        self.editor.inp_end.setText("00:00:04,000")
        self.editor._apply_current_editor()
        self.assertEqual(self.editor.all_segments[0]["end"], 4000)
        self.assertEqual(self.editor.lbl_duration.text(), "3.000 s")
        self.undo_manager.undo()
        self.assertEqual(self.editor.all_segments[0]["end"], 3000)
        self.assertEqual(self.editor.lbl_duration.text(), "2.000 s")

    def test_07_invalid_timing_does_not_push_command(self):
        self.editor.select_segment(0)
        initial_stack_count = self.undo_manager.undo_stack.count()
        self.editor.inp_start.setText("00:00:05,000")
        self.editor._apply_current_editor()
        self.assertEqual(self.undo_manager.undo_stack.count(), initial_stack_count)
        self.assertEqual(self.editor.all_segments[0]["start"], 1000)

    def tearDown(self):
        self.editor.close()


if __name__ == "__main__":
    unittest.main()
