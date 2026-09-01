from core.subtitle_editing.commands.base_command import SubtitleCommand


class MergeCommand(SubtitleCommand):
    def __init__(self, segment_index: int, data_provider: list):
        super().__init__("Gộp Subtitle", data_provider)
        self.segment_index = segment_index
        self.original_seg1 = None
        self.original_seg2 = None

    def redo(self):
        self.original_seg1 = self.data_provider[self.segment_index].copy()
        self.original_seg2 = self.data_provider.pop(self.segment_index + 1)
        self.data_provider[self.segment_index]["end"] = self.original_seg2["end"]
        merged_text = f"{self.original_seg1['text'].strip()} {self.original_seg2['text'].strip()}".strip()
        self.data_provider[self.segment_index]["text"] = merged_text

    def undo(self):
        self.data_provider[self.segment_index] = self.original_seg1.copy()
        self.data_provider.insert(self.segment_index + 1, self.original_seg2.copy())
