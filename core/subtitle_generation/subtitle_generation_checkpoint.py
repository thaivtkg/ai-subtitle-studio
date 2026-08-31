from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SubtitleGenerationCheckpoint:
    project_id: str
    source_fingerprint: str
    request_id: str
    subtitle_artifact_id: str
    artifact_revision: int
    completed_batches: List[str]
    request_data: Dict
    batches_data: List[Dict]
    active_batch: Optional[Dict]
    next_start_ms: int
    detected_language: Optional[str]
    updated_at: str
    status: str = "RUNNING"
    # SHA-256 of the canonical subtitle JSON at the last committed checkpoint.
    artifact_content_hash: Optional[str] = None
