from dataclasses import dataclass, field
from core.project.project_state import ProjectState
from core.project.transcription_context import TranscriptionContext

@dataclass
class SourceInfo:
    """Định danh file video gốc, chống việc người dùng tráo đổi file làm hỏng Timing"""
    path: str
    filename: str
    size_bytes: int
    modified_at: float
    fingerprint: str  # Hash hoặc tổ hợp size + mtime

@dataclass
class Project:
    """Thực thể gốc của toàn bộ Workspace"""
    project_id: str
    name: str
    created_at: str
    updated_at: str
    
    source: SourceInfo
    state: ProjectState
    transcription_context: TranscriptionContext = field(default_factory=TranscriptionContext)
    schema_version: int = 2
