from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from core.timing.timing_batch import TimingBatch, BatchStatus

@dataclass
class TimingCheckpoint:
    project_id: str
    source_fingerprint: str
    timing_artifact_id: str
    timing_revision: int
    batch_size: int
    
    # [FIX-02] Lưu trữ object active_batch thay vì chỉ là ID chuỗi
    active_batch: Optional[Dict[str, Any]] = None 
    
    next_segment_index: int = 1
    last_completed_end_ms: int = 0
    completed_batches: List[str] = field(default_factory=list)
    updated_at: str = ""