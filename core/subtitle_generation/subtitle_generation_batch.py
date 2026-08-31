from dataclasses import dataclass


@dataclass
class SubtitleGenerationBatch:
    """A time range sent to Whisper; boundaries are independent of segment count."""

    batch_id: str
    start_ms: int
    end_ms: int
    status: str  # PENDING, RUNNING, COMPLETED, FAILED, STALE
    revision: int
    created_at: str
    updated_at: str
