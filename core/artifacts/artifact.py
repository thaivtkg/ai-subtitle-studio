from dataclasses import dataclass, field
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus

@dataclass
class Artifact:
    """Một đơn vị tài nguyên có giá trị độc lập trong Project"""
    artifact_id: str
    artifact_type: ArtifactType
    path: str
    created_at: str
    updated_at: str
    source_project_id: str
    
    status: ArtifactStatus
    revision: int = 1  # Revision cực kỳ quan trọng cho tính năng Continue/Batch sau này
    metadata: dict = field(default_factory=dict)