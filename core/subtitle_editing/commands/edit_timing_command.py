from core.subtitle_editing.commands.base_command import SubtitleCommand


class EditTimingCommand(SubtitleCommand):
    def __init__(
        self,
        segment_index: int,
        old_start,
        old_end,
        new_start,
        new_end,
        data_provider: list,
    ):
        super().__init__("Sửa thời gian", data_provider)
        self.segment_index = segment_index
        self.old_start = old_start
        self.old_end = old_end
        self.new_start = new_start
        self.new_end = new_end

    def undo(self):
        segment = self.data_provider[self.segment_index]
        segment["start"] = self.old_start
        segment["end"] = self.old_end

    def redo(self):
        segment = self.data_provider[self.segment_index]
        segment["start"] = self.new_start
        segment["end"] = self.new_end
