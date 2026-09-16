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

    # Result-affecting settings needed to resume the exact same Timing run.
    # None marks a legacy checkpoint that predates settings persistence.
    model_size: Optional[str] = None
    compute_type: Optional[str] = None
    use_vad: Optional[bool] = None
    min_silence_ms: Optional[int] = None
    fix_overlap: Optional[bool] = None
    overlap_gap_ms: Optional[int] = None
    overlap_ms: Optional[int] = None
    max_window_ms: Optional[int] = None
    
    next_segment_index: int = 1
    last_completed_end_ms: int = 0
    completed_batches: List[str] = field(default_factory=list)
    updated_at: str = ""
