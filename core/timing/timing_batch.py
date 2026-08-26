from dataclasses import dataclass
from enum import Enum

class BatchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass
class TimingBatch:
    """Đại diện cho một khối công việc (Batch) cụ thể"""
    batch_id: str
    start_segment: int
    end_segment: int
    start_ms: int
    end_ms: int
    status: BatchStatus
    revision: int
    created_at: str
    updated_at: str