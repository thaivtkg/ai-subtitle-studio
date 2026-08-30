from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class GenerationCheckpoint:
    project_id: str
    source_fingerprint: str
    
    timing_artifact_id: str
    text_artifact_id: str
    
    timing_revision: int  # Tách bạch rõ ràng
    text_revision: int    # Theo dõi vòng đời của chữ
    
    next_segment_index: int
    completed_batches: List[str]
    
    request_data: Dict
    batches_data: List[Dict]
    
    active_batch: Optional[Dict]
    updated_at: str
    status: str = "RUNNING"