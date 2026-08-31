import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch


class SubtitleGenerationPlanner:
    """Partitions a source duration into deterministic, overlapping ranges.

    Segment mode groups the real timing ranges from a completed Timing
    Artifact. The reconciler remains responsible for boundary cleanup.
    """

    @staticmethod
    def create_plan(
        duration_ms: int,
        batch_mode: str = "time",
        size_value: int = 5,
        overlap_ms: int = 2000,
        batch_duration_ms: Optional[int] = None,
        segment_ranges: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> List[SubtitleGenerationBatch]:
        if batch_duration_ms is not None:
            # Backward-compatible support for the former named argument.
            batch_mode = "time"
            size_value = max(1, (int(batch_duration_ms) + 59999) // 60000)

        # Backward-compatible support for the old call shape:
        # create_plan(duration_ms, batch_duration_ms, overlap_ms).
        if isinstance(batch_mode, (int, float)):
            legacy_duration_ms = int(batch_mode)
            legacy_overlap_ms = int(size_value)
            batch_mode = "time"
            size_value = max(1, (legacy_duration_ms + 59999) // 60000)
            overlap_ms = legacy_overlap_ms

        if duration_ms <= 0 or size_value <= 0:
            return []
        if batch_mode not in {"time", "segments"}:
            raise ValueError("batch_mode must be 'time' or 'segments'")

        if batch_mode == "segments":
            if not segment_ranges:
                raise ValueError(
                    "Segment-based batching requires a completed Timing Artifact."
                )
            return SubtitleGenerationPlanner._create_segment_plan(
                duration_ms, int(size_value), int(overlap_ms), segment_ranges
            )

        batch_duration_ms = size_value * 60 * 1000
        if overlap_ms < 0 or overlap_ms >= batch_duration_ms:
            raise ValueError(
                "overlap_ms must be >= 0 and smaller than the estimated batch duration"
            )

        batches: List[SubtitleGenerationBatch] = []
        start_ms = 0
        while start_ms < duration_ms:
            end_ms = min(start_ms + batch_duration_ms + overlap_ms, duration_ms)
            now = datetime.now(timezone.utc).isoformat()
            batches.append(
                SubtitleGenerationBatch(
                    batch_id=str(uuid.uuid4()),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    status="PENDING",
                    revision=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            if end_ms >= duration_ms:
                break
            start_ms += batch_duration_ms
        return batches

    @staticmethod
    def _create_segment_plan(
        duration_ms: int,
        batch_size: int,
        overlap_ms: int,
        segment_ranges: Sequence[Tuple[int, int]],
    ) -> List[SubtitleGenerationBatch]:
        """Group actual Timing Artifact ranges by segment count."""
        if duration_ms <= 0 or batch_size <= 0:
            return []
        if overlap_ms < 0:
            raise ValueError("overlap_ms must be non-negative")

        normalized: List[Tuple[int, int]] = []
        for start_ms, end_ms in segment_ranges:
            start = max(0, int(start_ms))
            end = min(duration_ms, int(end_ms))
            if end > start:
                normalized.append((start, end))
        normalized.sort()
        if not normalized:
            return []

        batches: List[SubtitleGenerationBatch] = []
        for index in range(0, len(normalized), batch_size):
            group = normalized[index : index + batch_size]
            start_ms = max(0, group[0][0] - overlap_ms)
            end_ms = min(duration_ms, group[-1][1] + overlap_ms)
            now = datetime.now(timezone.utc).isoformat()
            batches.append(
                SubtitleGenerationBatch(
                    batch_id=str(uuid.uuid4()),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    status="PENDING",
                    revision=0,
                    created_at=now,
                    updated_at=now,
                )
            )
        return batches
