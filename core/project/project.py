from dataclasses import dataclass
from core.project.project_state import ProjectState

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
    
    schema_version: int = 1