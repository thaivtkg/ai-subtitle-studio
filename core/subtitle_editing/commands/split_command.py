from core.subtitle_editing.commands.base_command import SubtitleCommand


class SplitCommand(SubtitleCommand):
    def __init__(self, segment_index: int, split_time_ms: int, data_provider: list):
        super().__init__("Tách Subtitle", data_provider)
        self.segment_index = segment_index
        self.split_time_ms = split_time_ms
        self.original_seg = None
        self.new_segment = None

    def _split_text_at_midpoint(self, text: str) -> tuple[str, str]:
        if not text:
            return "", ""
        text = text.strip()
        if len(text) <= 1:
            return text, ""
        midpoint = len(text) // 2

        # 1. Ưu tiên dấu cách (space/tab)
        spaces = [index for index, char in enumerate(text) if char.isspace()]
        if spaces:
            best_space = min(spaces, key=lambda index: abs(index - midpoint))
            return text[:best_space].strip(), text[best_space:].strip()

        # 2. Ưu tiên dấu ngắt câu CJK & quốc tế (tách ngay sau dấu câu)
        cjk_puncts = "、。，！？!?…;；,"
        puncts = [index + 1 for index, char in enumerate(text[:-1]) if char in cjk_puncts]
        if puncts:
            best_punct = min(puncts, key=lambda index: abs(index - midpoint))
            return text[:best_punct].strip(), text[best_punct:].strip()

        # 3. Fallback cho chuỗi không dấu cách (tiếng Nhật/Trung): cắt đôi chuỗi
        return text[:midpoint].strip(), text[midpoint:].strip()

    def redo(self):
        if self.original_seg is None:
            self.original_seg = self.data_provider[self.segment_index].copy()
        text1, text2 = self._split_text_at_midpoint(self.original_seg["text"])

        start_val = self.original_seg.get("start")
        if isinstance(start_val, str):
            from ui.SubEditor import ms_to_time_str
            split_end = ms_to_time_str(self.split_time_ms)
        else:
            split_end = self.split_time_ms

        self.data_provider[self.segment_index]["end"] = split_end
        self.data_provider[self.segment_index]["text"] = text1
        if "start_ms" in self.original_seg:
            self.data_provider[self.segment_index]["end_ms"] = self.split_time_ms

        if self.new_segment is None:
            self.new_segment = self.original_seg.copy()
            self.new_segment["start"] = split_end
            self.new_segment["end"] = self.original_seg["end"]
            self.new_segment["text"] = text2
            if "start_ms" in self.original_seg:
                self.new_segment["start_ms"] = self.split_time_ms
                self.new_segment["end_ms"] = self.original_seg.get("end_ms", self.split_time_ms)
            if "id" in self.new_segment:
                import uuid
                self.new_segment["id"] = uuid.uuid4().hex

        self.data_provider.insert(self.segment_index + 1, self.new_segment)
        self._renumber_stt()

    def undo(self):
        self.data_provider.pop(self.segment_index + 1)
        self.data_provider[self.segment_index] = self.original_seg.copy()
        self._renumber_stt()
