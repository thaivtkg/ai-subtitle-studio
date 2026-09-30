"""Pure timing reconciliation for generated subtitles in an uncovered range."""

import copy
from dataclasses import dataclass
from enum import Enum

from core.subtitle_generation.generation_range import GenerationRange
from core.timeline.timeline_commands import MIN_DURATION_MS


class ReconciliationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY_RESULT = "EMPTY_RESULT"
    CONFLICT = "CONFLICT"
    STALE_RANGE_CONFLICT = "STALE_RANGE_CONFLICT"


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    segments: tuple = ()
    global_shift_ms: int = 0
    boundary_clamps: int = 0
    overlap_repairs: int = 0
    changed_segment_count: int = 0
    reason: str = ""


def _value(segment, key):
    if isinstance(segment, dict):
        return segment.get(key)
    if hasattr(segment, "get_raw_dict"):
        return segment.get_raw_dict().get(key)
    return getattr(segment, key, None)


def _interval(segment, duration_ms):
    try:
        start = max(0, min(duration_ms, int(_value(segment, "start_ms"))))
        end = max(0, min(duration_ms, int(_value(segment, "end_ms"))))
    except (TypeError, ValueError, OverflowError):
        return None
    return (start, end) if end > start else None


def _copy_with_times(segment, start_ms, end_ms, global_shift_ms):
    result = dict(segment) if isinstance(segment, dict) else copy.copy(segment)
    try:
        result["start_ms"], result["end_ms"] = start_ms, end_ms
    except TypeError:
        try:
            result.start_ms, result.end_ms = start_ms, end_ms
        except (AttributeError, TypeError):
            raise ValueError("Generated timing result cannot be copied safely.")

    words = _value(segment, "words")
    if isinstance(words, (list, tuple)):
        adjusted_words = []
        for word in words:
            if not isinstance(word, dict) or not {"start_ms", "end_ms"}.issubset(word):
                adjusted_words.append(word)
                continue
            try:
                word_start = int(word["start_ms"]) + global_shift_ms
                word_end = int(word["end_ms"]) + global_shift_ms
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Generated word timing is invalid.") from exc
            word_start = max(start_ms, word_start)
            word_end = min(end_ms, word_end)
            if word_end <= word_start:
                raise ValueError("Boundary adjustment would invalidate word timing.")
            adjusted_word = dict(word)
            adjusted_word.update(start_ms=word_start, end_ms=word_end)
            adjusted_words.append(adjusted_word)
        try:
            if isinstance(result, dict):
                result["words"] = type(words)(adjusted_words)
            else:
                result.words = type(words)(adjusted_words)
        except (AttributeError, TypeError):
            raise ValueError("Generated word timing cannot be copied safely.")
    return result


def _conflict(reason, status=ReconciliationStatus.CONFLICT):
    return ReconciliationResult(status=status, reason=reason)


def reconcile_generated_timing(
    generation_range: GenerationRange,
    generated_segments,
    media_duration_ms: int,
    current_subtitles=(),
) -> ReconciliationResult:
    """Return a corrected copy, or a conflict without mutating either input."""
    raw_segments = list(generated_segments or ())
    if not raw_segments:
        return ReconciliationResult(
            status=ReconciliationStatus.EMPTY_RESULT,
            reason="No subtitle segments were generated for this range.",
        )

    try:
        duration = int(media_duration_ms)
        range_start = int(generation_range.start_ms)
        range_end = int(generation_range.end_ms)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return _conflict("Generation range or media duration is invalid.")
    if duration <= 0 or range_start < 0 or range_end <= range_start or range_end > duration:
        return _conflict("Generation range is outside media bounds.")

    raw_times = []
    for segment in raw_segments:
        try:
            start, end = int(_value(segment, "start_ms")), int(_value(segment, "end_ms"))
        except (TypeError, ValueError, OverflowError):
            return _conflict("Generated subtitle timing is not finite integer data.")
        if end <= start:
            return _conflict("Generated subtitle has zero or negative duration.")
        raw_times.append((start, end))
    if any(raw_times[index][0] > raw_times[index + 1][0] for index in range(len(raw_times) - 1)):
        return _conflict("Generated subtitle order is not chronological.")

    intervals = [
        interval
        for segment in current_subtitles or ()
        if (interval := _interval(segment, duration)) is not None
    ]
    if any(start < range_end and end > range_start for start, end in intervals):
        return _conflict(
            "Current subtitle coverage intersects the selected range.",
            ReconciliationStatus.STALE_RANGE_CONFLICT,
        )

    previous_end = max(
        (end for _start, end in intervals if end <= range_start), default=0
    )
    next_start = min(
        (start for start, _end in intervals if start >= range_end), default=duration
    )
    safe_start = max(range_start, previous_end)
    safe_end = min(range_end, next_start)
    if safe_end <= safe_start:
        return _conflict("No safe uncovered timing window remains.")

    candidate_times = list(raw_times)
    batch_start = min(start for start, _end in candidate_times)
    batch_end = max(end for _start, end in candidate_times)
    shift_low = safe_start - batch_start
    shift_high = safe_end - batch_end
    shift = 0
    clamps = 0

    if shift_low <= shift_high:
        shift = max(shift_low, min(0, shift_high))
        candidate_times = [(start + shift, end + shift) for start, end in candidate_times]
    else:
        for index, (start, end) in enumerate(candidate_times):
            if end <= safe_start or start >= safe_end:
                return _conflict("A generated subtitle lies wholly outside the safe range.")
            if start < safe_start:
                start = safe_start
                clamps += 1
            if end > safe_end:
                end = safe_end
                clamps += 1
            if end - start < MIN_DURATION_MS:
                return _conflict("Boundary clamp would violate the canonical minimum duration.")
            candidate_times[index] = (start, end)

    if any(
        start < safe_start or end > safe_end or end - start < MIN_DURATION_MS
        for start, end in candidate_times
    ):
        return _conflict("Reconciled timing violates range bounds or minimum duration.")

    repairs = 0
    for index in range(len(candidate_times) - 1):
        start, end = candidate_times[index]
        next_segment_start, next_end = candidate_times[index + 1]
        if end <= next_segment_start:
            continue
        boundary = round((end + next_segment_start) / 2)
        if boundary - start < MIN_DURATION_MS or next_end - boundary < MIN_DURATION_MS:
            return _conflict("Overlap repair would violate the canonical minimum duration.")
        candidate_times[index] = (start, boundary)
        candidate_times[index + 1] = (boundary, next_end)
        repairs += 1

    if any(
        start < safe_start
        or end > safe_end
        or end - start < MIN_DURATION_MS
        or (index and candidate_times[index - 1][1] > start)
        for index, (start, end) in enumerate(candidate_times)
    ):
        return _conflict("Final generated timing validation failed.")

    try:
        reconciled = tuple(
            _copy_with_times(segment, start, end, shift)
            for segment, (start, end) in zip(raw_segments, candidate_times)
        )
    except ValueError as exc:
        return _conflict(str(exc))

    changed = sum(before != after for before, after in zip(raw_times, candidate_times))
    return ReconciliationResult(
        status=ReconciliationStatus.SUCCESS,
        segments=reconciled,
        global_shift_ms=shift,
        boundary_clamps=clamps,
        overlap_repairs=repairs,
        changed_segment_count=changed,
    )
