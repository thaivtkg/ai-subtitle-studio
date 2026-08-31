import re
from typing import Dict, List

from core.subtitle_generation.subtitle_generation_result import WhisperSegmentResult


class BoundaryReconciler:
    """Removes overlap duplicates deterministically without changing source text."""

    _TAIL_SIZE = 10
    _MAX_START_DIFF_MS = 3000

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.casefold()).strip()

    @classmethod
    def reconcile(
        cls,
        existing_segments: List[Dict],
        new_segments: List[WhisperSegmentResult],
    ) -> List[WhisperSegmentResult]:
        if not new_segments:
            return []
        if not existing_segments:
            return list(new_segments)

        tail = existing_segments[-cls._TAIL_SIZE :]
        reconciled: List[WhisperSegmentResult] = []
        for segment in new_segments:
            normalized = cls._normalize(segment.text)
            duplicate = any(
                normalized
                and normalized == cls._normalize(previous.get("text", ""))
                and abs(segment.start_ms - int(previous.get("start_ms", 0)))
                <= cls._MAX_START_DIFF_MS
                for previous in tail
            )
            if not duplicate:
                reconciled.append(segment)
        return reconciled
