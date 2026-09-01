import unittest

from core.recovery.revision_tracker import RevisionTracker
from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager


class TestRevisionTracker(unittest.TestCase):
    def setUp(self):
        self.data = [{"id": "a", "stt": "1", "start": 0, "end": 1000, "text": "A"}]
        self.undo = GlobalUndoManager()
        self.tracker = RevisionTracker(self.undo)

    def test_tc85_push_undo_redo_are_monotonic_once_each(self):
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.assertEqual(self.tracker.edit_revision, 1)
        self.undo.undo()
        self.assertEqual(self.tracker.edit_revision, 2)
        self.undo.redo()
        self.assertEqual(self.tracker.edit_revision, 3)

    def test_tc86_undo_to_saved_point_records_clean_revision(self):
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.tracker.record_explicit_save_success()
        saved_revision = self.tracker.last_saved_revision

        self.undo.push(EditTextCommand(0, "B", "C", self.data))
        self.undo.undo()

        self.assertGreater(self.tracker.last_clean_revision, saved_revision)
        self.assertFalse(self.tracker.is_dirty)

    def test_tc87_clean_changed_does_not_double_increment(self):
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.tracker.record_explicit_save_success()

        self.undo.push(EditTextCommand(0, "B", "C", self.data))
        before = self.tracker.edit_revision
        self.undo.undo()

        self.assertEqual(self.tracker.edit_revision, before + 1)

    def test_tc88_recovered_empty_stack_is_still_dirty(self):
        self.tracker.restore_from_snapshot(10, 4, 4)
        self.assertTrue(self.undo.undo_stack.isClean())
        self.assertTrue(self.tracker.is_dirty)
        self.assertEqual(self.tracker.edit_revision, 10)

    def test_tc89_undo_to_recovered_baseline_stays_dirty(self):
        self.tracker.restore_from_snapshot(10, 4, 4)
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.undo.undo()

        self.assertTrue(self.tracker.recovered_dirty_baseline)
        self.assertTrue(self.tracker.is_dirty)
        self.assertEqual(self.tracker.last_clean_revision, 4)


if __name__ == "__main__":
    unittest.main()
