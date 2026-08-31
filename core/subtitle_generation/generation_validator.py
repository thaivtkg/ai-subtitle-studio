from typing import List

from core.subtitle_generation.subtitle_generation_result import WhisperSegmentResult


class SubtitleGenerationValidator:
    """Filters malformed and known hallucinated ASR output."""

    HALLUCINATIONS = (
        "transcription by",
        "castingwords",
        "amara.org",
        "subtitles by",
        "subtitle by",
        "translated by",
        "subs by",
        "đăng ký kênh",
    )

    @staticmethod
    def validate(
        segments: List[WhisperSegmentResult], batch_start_ms: int, batch_end_ms: int
    ) -> List[WhisperSegmentResult]:
        if batch_start_ms < 0 or batch_end_ms <= batch_start_ms:
            return []

        valid: List[WhisperSegmentResult] = []
        for segment in segments:
            text = (segment.text or "").strip()
            if (
                segment.start_ms < 0
                or segment.end_ms <= segment.start_ms
                or not text
                or segment.start_ms > batch_end_ms
                or segment.end_ms < batch_start_ms
            ):
                continue
            if any(
                phrase in text.casefold()
                for phrase in SubtitleGenerationValidator.HALLUCINATIONS
            ):
                continue
            valid.append(segment)
        return valid
