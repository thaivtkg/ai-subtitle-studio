"""Transient time range and uncovered-coverage validation for range generation."""

import re
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace

from core.timeline.gaps import find_timeline_gaps


class GenerationRangeStatus(str, Enum):
    VALID = "VALID"
    NO_MEDIA = "NO_MEDIA"
    INVALID_FORMAT = "INVALID_FORMAT"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    EMPTY_OR_REVERSED = "EMPTY_OR_REVERSED"
    OVERLAPS_SUBTITLE = "OVERLAPS_SUBTITLE"


@dataclass(frozen=True)
class GenerationRange:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True)
class GenerationRangeValidation:
    status: GenerationRangeStatus
    generation_range: GenerationRange | None = None


def parse_timecode_ms(value: str) -> int:
    match = (
        re.fullmatch(r"(\d+):(\d{2}):(\d{2}),(\d{3})", value.strip())
        if isinstance(value, str)
        else None
    )
    if not match:
        raise ValueError("Invalid timecode")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Invalid timecode")
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds


def validate_generation_range(
    start_ms, end_ms, duration_ms: int, subtitle_segments=()
) -> GenerationRangeValidation:
    if duration_ms <= 0:
        return GenerationRangeValidation(GenerationRangeStatus.NO_MEDIA)
    try:
        start_ms, end_ms = int(start_ms), int(end_ms)
    except (TypeError, ValueError, OverflowError):
        return GenerationRangeValidation(GenerationRangeStatus.INVALID_FORMAT)
    if start_ms < 0 or end_ms > duration_ms:
        return GenerationRangeValidation(GenerationRangeStatus.OUT_OF_BOUNDS)
    if end_ms <= start_ms:
        return GenerationRangeValidation(GenerationRangeStatus.EMPTY_OR_REVERSED)

    generation_range = GenerationRange(start_ms, end_ms)
    coverage_segments = []
    for index, segment in enumerate(subtitle_segments or ()):
        if isinstance(segment, dict):
            start = segment.get("start_ms")
            end = segment.get("end_ms")
            segment_id = segment.get("id", index)
        else:
            start = getattr(segment, "start_ms", None)
            end = getattr(segment, "end_ms", None)
            segment_id = getattr(segment, "segment_id", index)
        coverage_segments.append(
            SimpleNamespace(start_ms=start, end_ms=end, segment_id=segment_id)
        )

    if not any(
        gap.start_ms <= start_ms and end_ms <= gap.end_ms
        for gap in find_timeline_gaps(duration_ms, coverage_segments)
    ):
        return GenerationRangeValidation(
            GenerationRangeStatus.OVERLAPS_SUBTITLE, generation_range
        )
    return GenerationRangeValidation(GenerationRangeStatus.VALID, generation_range)
