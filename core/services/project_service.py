import os
import json
import uuid
from datetime import datetime
from dataclasses import asdict

from core.project.project import Project, SourceInfo
from core.project.project_state import ProjectState, WorkspaceState
from core.artifacts.artifact_store import ArtifactStore
from core.utils.file_utils import atomic_save_json

class ProjectService:
    """Service điều phối toàn bộ Vòng đời của Dự án (Tạo, Lưu, Mở, Đóng)"""
    
    def __init__(self, artifact_store: ArtifactStore):
        self.artifact_store = artifact_store
        self.current_project: Project | None = None
        self.project_dir: str | None = None

    def _generate_fingerprint(self, video_path: str) -> SourceInfo:
        """Tạo định danh và vân tay cho file video gốc"""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video nguồn: {video_path}")
        
        stat = os.stat(video_path)
        size = stat.st_size
        mtime = stat.st_mtime
        fingerprint = f"{size}_{mtime}" # Thuật toán vân tay siêu nhẹ: Kích thước + Thời gian sửa đổi
        
        return SourceInfo(
            path=video_path,
            filename=os.path.basename(video_path),
            size_bytes=size,
            modified_at=mtime,
            fingerprint=fingerprint
        )

    def create_project(self, project_dir: str, name: str, video_path: str) -> Project:
        """Tạo một Project mới hoàn toàn"""
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(os.path.join(project_dir, "artifacts"), exist_ok=True)
        
        source_info = self._generate_fingerprint(video_path)
        now_str = datetime.now().isoformat()
        
        self.current_project = Project(
            project_id=str(uuid.uuid4()),
            name=name,
            created_at=now_str,
            updated_at=now_str,
            source=source_info,
            state=ProjectState()
        )
        self.project_dir = project_dir
        self.artifact_store.clear()
        
        # Lưu ngay lập tức để khởi tạo cấu trúc file
        self.save_project()
        return self.current_project

    def save_project(self) -> None:
        """Lưu Project hiện tại xuống đĩa cứng, chia thành 3 file riêng biệt để tối ưu"""
        if not self.current_project or not self.project_dir:
            return
            
        self.current_project.updated_at = datetime.now().isoformat()
        
        # 1. Lưu project.json (Thông tin gốc, hiếm khi thay đổi)
        proj_data = {
            "schema_version": self.current_project.schema_version,
            "project_id": self.current_project.project_id,
            "name": self.current_project.name,
            "created_at": self.current_project.created_at,
            "updated_at": self.current_project.updated_at,
            "source": asdict(self.current_project.source)
        }
        atomic_save_json(os.path.join(self.project_dir, "project.json"), proj_data)
        
        # 2. Lưu state.json (Trạng thái Workflow, hay thay đổi)
        state_data = {
            "timing_status": self.current_project.state.timing_status,
            "text_status": self.current_project.state.text_status,
            "export_status": self.current_project.state.export_status,
            "active_artifact_id": self.current_project.state.active_artifact_id,
            "selected_segment_id": self.current_project.state.selected_segment_id,
            "dirty": False  # Xóa cờ dirty khi đã lưu
        }
        atomic_save_json(os.path.join(self.project_dir, "state.json"), state_data)
        
        # 3. Lưu workspace.json (Trạng thái UI/UX của người dùng)
        workspace_data = asdict(self.current_project.state.workspace)
        atomic_save_json(os.path.join(self.project_dir, "workspace.json"), workspace_data)
        
        self.current_project.state.dirty = False

    def open_project(self, project_dir: str) -> Project:
        """Đọc và khôi phục Project từ thư mục"""
        proj_file = os.path.join(project_dir, "project.json")
        state_file = os.path.join(project_dir, "state.json")
        workspace_file = os.path.join(project_dir, "workspace.json")
        
        if not os.path.exists(proj_file):
            raise FileNotFoundError("Thư mục này không phải là một Project AI Subtitle Studio hợp lệ.")
            
        # 1. Đọc Project Info
        with open(proj_file, 'r', encoding='utf-8') as f:
            p_data = json.load(f)
            
        source_info = SourceInfo(**p_data["source"])
        
        # 2. Đọc State (Nếu có)
        project_state = ProjectState()
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
                project_state.timing_status = s_data.get("timing_status", "EMPTY")
                project_state.text_status = s_data.get("text_status", "EMPTY")
                project_state.export_status = s_data.get("export_status", "EMPTY")
                project_state.active_artifact_id = s_data.get("active_artifact_id")
                project_state.selected_segment_id = s_data.get("selected_segment_id")
        
        # 3. Đọc Workspace (Nếu có)
        if os.path.exists(workspace_file):
            with open(workspace_file, 'r', encoding='utf-8') as f:
                w_data = json.load(f)
                # Parse an toàn vào Dataclass
                project_state.workspace = WorkspaceState(**{k: v for k, v in w_data.items() if k in WorkspaceState.__dataclass_fields__})
                
        self.current_project = Project(
            project_id=p_data["project_id"],
            name=p_data["name"],
            created_at=p_data["created_at"],
            updated_at=p_data["updated_at"],
            source=source_info,
            state=project_state,
            schema_version=p_data.get("schema_version", 1)
        )
        self.project_dir = project_dir
        self.artifact_store.clear()
        
        # NOTE: Sẽ load các Artifacts từ đĩa cứng vào ArtifactStore ở các Phase sau
        
        return self.current_project

    def close_project(self) -> None:
        """Đóng dự án, dọn dẹp bộ nhớ"""
        if self.current_project and self.current_project.state.dirty:
            # Ở UI sẽ gọi hàm kiểm tra dirty này để hiện bảng hỏi "Bạn có muốn lưu không?"
            pass
            
        self.current_project = None
        self.project_dir = None
        self.artifact_store.clear()

    def mark_dirty(self) -> None:
        """Đánh dấu Project đã bị thay đổi"""
        if self.current_project:
            self.current_project.state.dirty = True