from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class WorkspaceState:
    """Lưu trữ chính xác những gì người dùng đang làm việc (Session)"""
    active_page: str = "dashboard"
    active_tab: str = "ai_generation"
    selected_segment_id: Optional[int] = None
    playback_position_ms: int = 0
    splitter_sizes: List[int] = field(default_factory=lambda: [520, 300])
    subtitle_preview_enabled: bool = True

@dataclass
class ProjectState:
    """Lưu trữ tiến độ của dự án"""
    timing_status: str = "EMPTY"  # EMPTY, TIMING, DRAFT, READY, FAILED
    text_status: str = "EMPTY"
    export_status: str = "EMPTY"
    
    active_artifact_id: Optional[str] = None
    selected_segment_id: Optional[int] = None
    
    workspace: WorkspaceState = field(default_factory=WorkspaceState)
    dirty: bool = False  # Bật thành True khi có thay đổi chưa lưu