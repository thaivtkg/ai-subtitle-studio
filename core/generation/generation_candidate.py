from dataclasses import dataclass
from typing import List, Optional

@dataclass
class GenerationCandidate:
    segment_id: str
    source_text: str
    generated_text: str
    model_id: str
    request_id: str

    
    confidence: Optional[float]
    
    validation_status: str # PENDING, PASSED, FAILED
    validation_errors: List[str]