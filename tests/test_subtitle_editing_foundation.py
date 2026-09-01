import unittest

from core.subtitle_editing.commands.base_command import SubtitleCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.selection_controller import (
    SelectionSource,
    SubtitleSelectionController,
)


class CountingCommand(SubtitleCommand):
    def __init__(self):
        super().__init__("Count")
        self.value = 0

    def redo(self):
        self.value += 1

    def undo(self):
        self.value -= 1


class TestSubtitleEditingFoundation(unittest.TestCase):
    def test_selection_emits_none_when_cleared_and_skips_duplicate_state(self):
        controller = SubtitleSelectionController()
        changes = []
        controller.selection_changed.connect(lambda *args: changes.append(args))

        controller.select(2, "segment-2", SelectionSource.EDITOR)
        controller.select(2, "segment-2", SelectionSource.TIMELINE)
        controller.clear_selection(SelectionSource.PLAYBACK)

        self.assertEqual(
            changes,
            [
                (2, "segment-2", SelectionSource.EDITOR),
                (-1, None, SelectionSource.PLAYBACK),
            ],
        )
        self.assertEqual(controller.selected_index, -1)
        self.assertIsNone(controller.selected_segment_id)

    def test_global_undo_manager_runs_commands_and_tracks_dirty_state(self):
        manager = GlobalUndoManager()
        command = CountingCommand()
        state_changes = []
        manager.state_changed.connect(lambda: state_changes.append(None))

        manager.push(command)
        self.assertEqual(command.value, 1)
        self.assertTrue(manager.is_dirty)

        manager.mark_saved()
        self.assertFalse(manager.is_dirty)
        manager.undo()
        self.assertEqual(command.value, 0)
        self.assertTrue(manager.is_dirty)

        manager.redo()
        self.assertEqual(command.value, 1)
        self.assertEqual(len(state_changes), 3)


if __name__ == "__main__":
    unittest.main()
