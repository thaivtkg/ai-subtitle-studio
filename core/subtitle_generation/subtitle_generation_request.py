from dataclasses import dataclass
from typing import Optional


@dataclass
class SubtitleGenerationRequest:
    """Input contract for one subtitle generation run.

    ``batch_duration_ms`` is retained as a deprecated input-only compatibility
    field so checkpoints and integrations created before the batching-mode
    migration can still be resumed safely.
    """

    request_id: str
    project_id: str
    source_fingerprint: str
    video_path: str
    model_size: str
    compute_type: str
    language: Optional[str]  # None means auto-detect.
    use_vad: bool
    min_silence_ms: int
    word_timestamps: bool
    batch_mode: str = "time"
    batch_size_value: int = 5
    overlap_ms: int = 2000
    batch_duration_ms: Optional[int] = None
    prompt_context: str = ""

    def __post_init__(self) -> None:
        if self.batch_mode not in {"time", "segments"}:
            raise ValueError("batch_mode must be 'time' or 'segments'")
        if self.batch_size_value <= 0:
            raise ValueError("batch_size_value must be positive")

        # Migrate the former ``batch_duration_ms`` contract when an old
        # request/checkpoint is loaded without explicit batching fields.
        if self.batch_duration_ms is not None and self.batch_mode == "time":
            if self.batch_size_value == 5:
                self.batch_size_value = max(
                    1, (int(self.batch_duration_ms) + 59999) // 60000
                )
