"""Validated, display-only time range filtering for subtitle segments.

Time ranges are represented as a half-open interval [start_ms, end_ms). This
module never mutates the subtitle source sequence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence


_MINUTE_RE = re.compile(r"^(?:\d+(?:[.,]\d+)?|[.,]\d+)$")
_TIMESTAMP_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


class TimeRangeValidationError(ValueError):
    """Raised when a minute-based time filter is missing or invalid."""


@dataclass(frozen=True)
class SubtitleTimeRange:
    """A half-open video-time range in milliseconds."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be non-negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")


def _parse_minutes(raw: str, label: str) -> float:
    text = (raw or "").strip()
    if not text:
        raise TimeRangeValidationError(f"Vui lòng nhập {label} (tính bằng phút).")
    if not _MINUTE_RE.fullmatch(text):
        raise TimeRangeValidationError(
            f"{label.capitalize()} không hợp lệ. Hãy nhập số phút không âm, ví dụ 0, 1.5 hoặc 2.25."
        )
    value = float(text.replace(",", "."))
    if not math.isfinite(value) or value < 0:
        raise TimeRangeValidationError(f"{label.capitalize()} phải là số không âm.")
    return value


def parse_minute_range(
    start_text: str | None,
    end_text: str | None,
    *,
    max_duration_ms: int | None = None,
) -> SubtitleTimeRange | None:
    """Validate two minute inputs and convert to milliseconds.

    Both fields blank means the user requested no time filter. A partial range is
    invalid. If the video's duration is known, the end must not exceed it.
    Decimal minutes accept either dot or comma as the decimal separator.
    """
    start_raw = (start_text or "").strip()
    end_raw = (end_text or "").strip()
    if not start_raw and not end_raw:
        return None

    start_minutes = _parse_minutes(start_raw, "phút bắt đầu")
    end_minutes = _parse_minutes(end_raw, "phút kết thúc")
    start_ms = int(round(start_minutes * 60_000))
    end_ms = int(round(end_minutes * 60_000))

    if end_ms <= start_ms:
        raise TimeRangeValidationError(
            "Phút kết thúc phải lớn hơn Phút bắt đầu."
        )
    if max_duration_ms is not None and max_duration_ms > 0 and end_ms > int(max_duration_ms):
        duration_minutes = max_duration_ms / 60_000
        raise TimeRangeValidationError(
            f"Phút kết thúc vượt thời lượng video ({duration_minutes:.3f} phút)."
        )
    return SubtitleTimeRange(start_ms, end_ms)


def parse_segment_time_ms(segment: Mapping[str, Any], edge: str) -> int | None:
    """Read a segment edge as milliseconds, tolerating supported project formats."""
    raw = segment.get(edge)
    if raw is None:
        raw = segment.get(f"{edge}_ms")
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = int(raw)
        return value if value >= 0 else None
    match = _TIMESTAMP_RE.fullmatch(str(raw).strip())
    if not match:
        return None
    hours, minutes, seconds, millis = map(int, match.groups())
    if minutes >= 60 or seconds >= 60 or millis >= 1000:
        return None
    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + millis


def indices_for_time_range(
    segments: Sequence[Mapping[str, Any]],
    time_range: tuple[int, int] | SubtitleTimeRange | None,
) -> list[int]:
    """Return source indices whose subtitles intersect the range, preserving order.

    Invalid-timing subtitles with a parseable start edge are retained when their
    start falls inside the range, so the user can still find and repair them.
    A segment that crosses either range boundary is included if it intersects the
    selected interval. Source data is never mutated.
    """
    if time_range is None:
        return list(range(len(segments)))
    if isinstance(time_range, SubtitleTimeRange):
        range_start_ms, range_end_ms = time_range.start_ms, time_range.end_ms
    else:
        range_start_ms, range_end_ms = map(int, time_range)
    if range_start_ms < 0 or range_end_ms <= range_start_ms:
        raise ValueError("time_range must be a valid non-negative interval")

    indices: list[int] = []
    for index, segment in enumerate(segments):
        start_ms = parse_segment_time_ms(segment, "start")
        if start_ms is None:
            continue
        end_ms = parse_segment_time_ms(segment, "end")
        if end_ms is None or end_ms <= start_ms:
            if range_start_ms <= start_ms < range_end_ms:
                indices.append(index)
            continue
        if start_ms < range_end_ms and end_ms > range_start_ms:
            indices.append(index)
    return indices
