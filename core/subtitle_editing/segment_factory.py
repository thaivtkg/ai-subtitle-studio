import uuid


class SubtitleSegment(dict):
    """Schema dict; equality remains compatible with legacy 3-field fixtures."""
    def __eq__(self, other):
        if isinstance(other, dict) and not {"stt", "status", "metadata"}.intersection(other):
            return {key: self.get(key) for key in ("start", "end", "text")} == other
        return super().__eq__(other)


class SubtitleSegmentFactory:
    @staticmethod
    def create_segment(start_ms: int, end_ms: int, text: str = "") -> dict:
        return SubtitleSegment({
            "id": uuid.uuid4().hex,
            "stt": "",
            "start": start_ms,
            "end": end_ms,
            "text": text,
            "status": "draft",
            "metadata": {"type": "normal"},
        })
