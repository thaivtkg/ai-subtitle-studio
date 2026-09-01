import unittest

from core.subtitle_editing.commands.add_command import AddCommand
from core.subtitle_editing.commands.delete_command import DeleteCommand
from core.subtitle_editing.commands.merge_command import MergeCommand
from core.subtitle_editing.commands.split_command import SplitCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager


class TestStructuralCommands(unittest.TestCase):
    def setUp(self):
        self.segments = [
            {"start": 0, "end": 1000, "text": "Hello"},
            {"start": 1000, "end": 2000, "text": "world"},
        ]
        self.manager = GlobalUndoManager()

    def test_delete_undo_redo_restores_exact_segment(self):
        original = self.segments[1].copy()
        self.manager.push(DeleteCommand(1, self.segments))
        self.assertEqual(self.segments, [{"start": 0, "end": 1000, "text": "Hello"}])
        self.manager.undo()
        self.assertEqual(self.segments[1], original)
        self.manager.redo()
        self.assertEqual(len(self.segments), 1)

    def test_add_undo_redo_reuses_same_segment(self):
        self.manager.push(AddCommand(1, 1000, 1500, self.segments))
        added = self.segments[1]
        self.assertEqual(added, {"start": 1000, "end": 1500, "text": ""})
        self.manager.undo()
        self.assertEqual(len(self.segments), 2)
        self.manager.redo()
        self.assertIs(self.segments[1], added)

    def test_merge_undo_redo_preserves_original_segments(self):
        self.manager.push(MergeCommand(0, self.segments))
        self.assertEqual(self.segments, [{"start": 0, "end": 2000, "text": "Hello world"}])
        self.manager.undo()
        self.assertEqual(self.segments[0]["text"], "Hello")
        self.assertEqual(self.segments[1]["text"], "world")
        self.manager.redo()
        self.assertEqual(len(self.segments), 1)

    def test_split_undo_redo_preserves_original_segment(self):
        self.segments = [{"start": 0, "end": 1000, "text": "Hello world again"}]
        self.manager.push(SplitCommand(0, 500, self.segments))
        self.assertEqual(self.segments[0], {"start": 0, "end": 500, "text": "Hello"})
        self.assertEqual(self.segments[1], {"start": 500, "end": 1000, "text": "world again"})
        self.manager.undo()
        self.assertEqual(self.segments, [{"start": 0, "end": 1000, "text": "Hello world again"}])
        self.manager.redo()
        self.assertEqual(len(self.segments), 2)


if __name__ == "__main__":
    unittest.main()
