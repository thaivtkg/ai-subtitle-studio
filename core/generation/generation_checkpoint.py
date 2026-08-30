from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class GenerationCheckpoint:
    project_id: str
    source_fingerprint: str
    
    timing_artifact_id: str
    text_artifact_id: str
    
    request_id: str
    generation_revision: int
    
    next_segment_index: int
    completed_batches: List[str]
    
    # LƯU TRỮ TOÀN BỘ SESSION STATE ĐỂ RESUME THẬT SỰ
    request_data: Dict
    batches_data: List[Dict]
    
    active_batch: Optional[Dict]
    updated_at: str
    status: str = "RUNNING" # RUNNING, CANCELLED, COMPLETED, FAILED