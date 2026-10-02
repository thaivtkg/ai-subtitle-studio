import unittest

from core.subtitle_editing.segment_factory import SubtitleSegmentFactory
from core.subtitle_editing.commands.add_command import AddCommand
from core.subtitle_editing.commands.split_command import SplitCommand
from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.commands.base_command import SubtitleCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.selection_controller import SubtitleSelectionController, SelectionSource
from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import Severity


class TestSprint10Regression(unittest.TestCase):
    def setUp(self):
        self.data_provider = [
            SubtitleSegmentFactory.create_segment(1000, 3000, "Hello World")
        ]
        self.required_keys = ["stt", "start", "end", "text", "status", "metadata"]

    def test_tc70_tc71_add_and_split_preserve_production_schema(self):
        add_cmd = AddCommand(1, 3000, 5000, self.data_provider)
        add_cmd.redo()
        for key in self.required_keys:
            self.assertIn(key, self.data_provider[1])

        split_cmd = SplitCommand(0, 2000, self.data_provider)
        split_cmd.redo()
        for key in self.required_keys:
            self.assertIn(key, self.data_provider[1])

    def test_tc72_save_srt_simulation_no_keyerror(self):
        SplitCommand(0, 2000, self.data_provider).redo()
        for seg in self.data_provider:
            for key in ("stt", "start", "end", "text"):
                _ = seg[key]

    def test_tc73_global_undo_interleaves_editor_and_timeline_correctly(self):
        undo_manager = GlobalUndoManager()
        undo_manager.push(EditTextCommand(0, "Hello World", "Edited Text", self.data_provider))

        class DummyTimelineResize(SubtitleCommand):
            def __init__(self, data):
                super().__init__("Timeline Resize", data)

            def redo(self):
                self.data_provider[0]["end"] = 4500

            def undo(self):
                self.data_provider[0]["end"] = 3000

        undo_manager.push(DummyTimelineResize(self.data_provider))
        self.assertEqual(self.data_provider[0]["text"], "Edited Text")
        self.assertEqual(self.data_provider[0]["end"], 4500)
        undo_manager.undo()
        self.assertEqual(self.data_provider[0]["end"], 3000)
        self.assertEqual(self.data_provider[0]["text"], "Edited Text")
        undo_manager.undo()
        self.assertEqual(self.data_provider[0]["text"], "Hello World")

    def test_tc74_selection_controller_broadcasts_to_all_views(self):
        controller = SubtitleSelectionController()
        received = []

        def sync_selection(index, segment_id, source):
            received.append(index)

        controller.selection_changed.connect(sync_selection)
        controller.selection_changed.connect(sync_selection)
        controller.select(5, "uuid-123", SelectionSource.EDITOR)
        self.assertEqual(received, [5, 5])

    def test_tc75_validator_catches_malformed_timestamp(self):
        issues = SubtitleValidator.validate_segment(
            0, {"start": "abc", "end": 1000, "text": "Lỗi định dạng"}
        )
        self.assertTrue(any(
            issue.severity == Severity.ERROR and issue.code == "INVALID_TIMESTAMP_FORMAT"
            for issue in issues
        ))


if __name__ == "__main__":
    unittest.main()
