from core.subtitle_editing.commands.base_command import SubtitleCommand


class EditTextCommand(SubtitleCommand):
    def __init__(self, segment_index: int, old_text: str, new_text: str, data_provider: list):
        super().__init__("Sửa nội dung", data_provider)
        self.segment_index = segment_index
        self.old_text = old_text
        self.new_text = new_text

    def id(self):
        return 1

    def mergeWith(self, other: SubtitleCommand) -> bool:
        if not isinstance(other, EditTextCommand) or self.segment_index != other.segment_index:
            return False
        self.new_text = other.new_text
        return True

    def undo(self):
        self.data_provider[self.segment_index]["text"] = self.old_text

    def redo(self):
        self.data_provider[self.segment_index]["text"] = self.new_text
