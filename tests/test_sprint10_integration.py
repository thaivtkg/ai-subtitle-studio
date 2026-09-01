import unittest

from core.subtitle_editing.segment_factory import SubtitleSegmentFactory
from core.subtitle_editing.commands.add_command import AddCommand
from core.subtitle_editing.commands.split_command import SplitCommand
from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.commands.timeline_adapter import TimelineCommandAdapter
from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import ValidationMode
from core.export.export_service import generate_srt_content


class TestSprint10Integration(unittest.TestCase):
    def setUp(self):
        self.data = [
            SubtitleSegmentFactory.create_segment(1000, 3000, "Segment 1"),
            SubtitleSegmentFactory.create_segment(4000, 6000, "Segment 2"),
        ]
        for i, segment in enumerate(self.data):
            segment["stt"] = str(i + 1)

    def test_tc76_add_renumbers_stt_and_preserves_unique_uuid(self):
        original_ids = {segment["id"] for segment in self.data}
        command = AddCommand(1, 3100, 3900, self.data)
        command.redo()
        self.assertEqual([segment["stt"] for segment in self.data], ["1", "2", "3"])
        self.assertTrue(self.data[1]["id"] not in original_ids)
        command.undo()
        self.assertEqual(self.data[1]["text"], "Segment 2")

    def test_tc77_tc78_split_and_save_srt_canonical_format(self):
        SplitCommand(0, 2000, self.data).redo()
        output = generate_srt_content(self.data)
        self.assertNotIn("uuid", output)
        self.assertIn("1\n00:00:01,000 --> 00:00:02,000", output)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,000", output)

    def test_tc79_global_undo_interleaving(self):
        manager = GlobalUndoManager()
        manager.push(EditTextCommand(0, "Segment 1", "Editor Changed", self.data))

        class TimelineCommand:
            def __init__(self, data): self.data_provider = data
            def redo(self): self.data_provider[0]["end"] = 5000
            def undo(self): self.data_provider[0]["end"] = 3000

        manager.push(TimelineCommandAdapter(TimelineCommand(self.data)))
        manager.undo()
        self.assertEqual(self.data[0]["text"], "Editor Changed")
        self.assertEqual(self.data[0]["end"], 3000)
        manager.undo()
        self.assertEqual(self.data[0]["text"], "Segment 1")

    def test_tc80_timing_draft_suppresses_empty_text(self):
        self.data[0]["text"] = ""
        full = SubtitleValidator.validate_segment(0, self.data[0], 10000, ValidationMode.FULL_SUBTITLE)
        draft = SubtitleValidator.validate_segment(0, self.data[0], 10000, ValidationMode.TIMING_DRAFT)
        self.assertTrue(any(issue.code == "EMPTY_TEXT" for issue in full))
        self.assertFalse(any(issue.code == "EMPTY_TEXT" for issue in draft))


if __name__ == "__main__":
    unittest.main()
