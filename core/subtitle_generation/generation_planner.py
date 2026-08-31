import uuid
from datetime import datetime, timezone
from typing import List, Optional

from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch


class SubtitleGenerationPlanner:
    """Partitions a source duration into deterministic, overlapping ranges.

    Segment mode is necessarily an estimate at planning time: transcription
    has not happened yet, so each requested segment is mapped to five seconds
    of source time. The reconciler remains responsible for boundary cleanup.
    """

    ESTIMATED_MS_PER_SEGMENT = 5000

    @staticmethod
    def create_plan(
        duration_ms: int,
        batch_mode: str = "time",
        size_value: int = 5,
        overlap_ms: int = 2000,
        batch_duration_ms: Optional[int] = None,
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

        batch_duration_ms = (
            size_value * 60 * 1000
            if batch_mode == "time"
            else size_value * SubtitleGenerationPlanner.ESTIMATED_MS_PER_SEGMENT
        )
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
