"""Derived uncovered intervals on a media timeline; no project mutation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineGap:
    start_ms: int
    end_ms: int
    previous_id: str | None
    next_id: str | None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def find_timeline_gaps(duration_ms: int, segments) -> list[TimelineGap]:
    if duration_ms <= 0:
        return []

    intervals = []
    for segment in segments:
        try:
            start = max(0, min(duration_ms, int(segment.start_ms)))
            end = max(0, min(duration_ms, int(segment.end_ms)))
        except (TypeError, ValueError, OverflowError):
            continue
        if end > start:
            intervals.append((start, end, segment.segment_id))
    intervals.sort(key=lambda item: (item[0], -item[1]))

    gaps = []
    covered_until = 0
    previous_id = None
    for start, end, segment_id in intervals:
        if start > covered_until:
            gaps.append(TimelineGap(covered_until, start, previous_id, segment_id))
        if end > covered_until:
            covered_until = end
            previous_id = segment_id
    if covered_until < duration_ms:
        gaps.append(TimelineGap(covered_until, duration_ms, previous_id, None))
    return gaps
