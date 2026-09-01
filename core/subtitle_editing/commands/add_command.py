from core.subtitle_editing.commands.base_command import SubtitleCommand
from core.subtitle_editing.segment_factory import SubtitleSegmentFactory


class AddCommand(SubtitleCommand):
    def __init__(self, segment_index: int, start_ms: int, end_ms: int, data_provider: list):
        super().__init__("Thêm Subtitle", data_provider)
        self.segment_index = segment_index
        self.new_segment = SubtitleSegmentFactory.create_segment(start_ms, end_ms)

    def redo(self):
        self.data_provider.insert(self.segment_index, self.new_segment)

    def undo(self):
        self.data_provider.pop(self.segment_index)
