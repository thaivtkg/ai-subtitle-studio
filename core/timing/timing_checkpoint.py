from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TimingCheckpoint:
    """Lưu trữ lịch sử an toàn của toàn bộ quá trình chia Batch (Lưu xuống đĩa)"""
    project_id: str
    source_fingerprint: str
    timing_artifact_id: str
    timing_revision: int
    batch_size: int
    active_batch_id: Optional[str] = None
    next_segment_index: int = 1
    last_completed_end_ms: int = 0
    completed_batches: List[str] = field(default_factory=list)
    updated_at: str = ""