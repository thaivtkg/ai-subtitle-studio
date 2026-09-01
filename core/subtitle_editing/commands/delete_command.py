from core.subtitle_editing.commands.base_command import SubtitleCommand


class DeleteCommand(SubtitleCommand):
    def __init__(self, segment_index: int, data_provider: list):
        super().__init__("Xóa Subtitle", data_provider)
        self.segment_index = segment_index
        self.deleted_segment = None

    def redo(self):
        self.deleted_segment = self.data_provider.pop(self.segment_index)
        self._renumber_stt()

    def undo(self):
        self.data_provider.insert(self.segment_index, self.deleted_segment)
        self._renumber_stt()
