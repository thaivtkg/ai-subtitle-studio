from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class RecoveryValidationResult:
    is_valid: bool
    reason: str = ""
    source_matches: bool = True
    source_reason: str = ""


@dataclass(frozen=True)
class RecoveryCandidate:
    manifest: "RecoveryManifest"
    snapshot: "RecoveryWorkingState"


@dataclass(frozen=True)
class RecoveryManifest:
    schema_version: int
    session_id: str
    app_version: str
    project_id: str
    project_file_path: str
    video_path: str
    source_fingerprint: str
    source_modified_at: float
    created_at: str
    last_snapshot_at: str
    edit_revision: int
    snapshot_revision: int
    last_saved_revision: int
    last_clean_revision: int


@dataclass(frozen=True)
class RecoveryWorkingState:
    schema_version: float
    session_id: str
    project_id: str
    project_file_path: str
    video_path: str
    source_fingerprint: str
    edit_revision: int
    segments: List[Dict[str, Any]] = field(default_factory=list)
    workspace_state: Dict[str, Any] = field(default_factory=dict)
