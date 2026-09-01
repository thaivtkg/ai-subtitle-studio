from core.subtitle_editing.commands.base_command import SubtitleCommand
from core.subtitle_editing.segment_factory import SubtitleSegmentFactory


class SplitCommand(SubtitleCommand):
    def __init__(self, segment_index: int, split_time_ms: int, data_provider: list):
        super().__init__("Tách Subtitle", data_provider)
        self.segment_index = segment_index
        self.split_time_ms = split_time_ms
        self.original_seg = None
        self.new_segment = None

    def _split_text_at_midpoint(self, text: str) -> tuple[str, str]:
        if not text or " " not in text:
            return text, ""
        midpoint = len(text) // 2
        spaces = [index for index, char in enumerate(text) if char == " "]
        best_space = min(spaces, key=lambda index: abs(index - midpoint))
        return text[:best_space].strip(), text[best_space:].strip()

    def redo(self):
        if self.original_seg is None:
            self.original_seg = self.data_provider[self.segment_index].copy()
        text1, text2 = self._split_text_at_midpoint(self.original_seg["text"])
        self.data_provider[self.segment_index]["end"] = self.split_time_ms
        self.data_provider[self.segment_index]["text"] = text1
        if self.new_segment is None:
            self.new_segment = SubtitleSegmentFactory.create_segment(
                self.split_time_ms, self.original_seg["end"], text2
            )
        self.data_provider.insert(self.segment_index + 1, self.new_segment)

    def undo(self):
        self.data_provider.pop(self.segment_index + 1)
        self.data_provider[self.segment_index] = self.original_seg.copy()
