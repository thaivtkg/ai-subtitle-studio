from core.subtitle_editing.commands.base_command import SubtitleCommand

class EditTimingCommand(SubtitleCommand):
    def __init__(
        self,
        segment_index_or_changes,
        old_start=None,
        old_end=None,
        new_start=None,
        new_end=None,
        data_provider=None,
    ):
        if isinstance(segment_index_or_changes, list):
            super().__init__("Sửa thời gian", data_provider)
            self.changes = segment_index_or_changes
        else:
            super().__init__("Sửa thời gian", data_provider)
            self.changes = [{
                "index": segment_index_or_changes,
                "old_start": old_start,
                "old_end": old_end,
                "new_start": new_start,
                "new_end": new_end
            }]

    @staticmethod
    def _to_ms(val):
        if isinstance(val, (int, float)):
            return int(val)
        try:
            h_m_s, ms = str(val).split(",")
            h, m, s = h_m_s.split(":")
            return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
        except Exception:
            return 0

    def undo(self):
        for c in self.changes:
            segment = self.data_provider[c["index"]]
            segment["start"] = c["old_start"]
            segment["end"] = c["old_end"]
            segment["start_ms"] = self._to_ms(c["old_start"])
            segment["end_ms"] = self._to_ms(c["old_end"])

    def redo(self):
        for c in self.changes:
            segment = self.data_provider[c["index"]]
            segment["start"] = c["new_start"]
            segment["end"] = c["new_end"]
            segment["start_ms"] = self._to_ms(c["new_start"])
            segment["end_ms"] = self._to_ms(c["new_end"])
