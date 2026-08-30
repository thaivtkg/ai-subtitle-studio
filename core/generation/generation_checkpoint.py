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
    
    active_batch: Optional[Dict]
    updated_at: str 