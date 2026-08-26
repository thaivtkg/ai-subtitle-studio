import os
import json
import uuid
from datetime import datetime
from dataclasses import asdict

from core.project.project import Project, SourceInfo
from core.project.project_state import ProjectState, WorkspaceState, TimingState
from core.artifacts.artifact_store import ArtifactStore
from core.utils.file_utils import atomic_save_json
from core.timing.timing_checkpoint import TimingCheckpoint

class ProjectService:
    """Service điều phối toàn bộ Vòng đời của Dự án (Tạo, Lưu, Mở, Đóng)"""
    
    def __init__(self, artifact_store: ArtifactStore):
        self.artifact_store = artifact_store
        self.current_project: Project | None = None
        self.project_dir: str | None = None

    def _generate_fingerprint(self, video_path: str) -> SourceInfo:
        """Tạo định danh và vân tay cho file video gốc bằng Fast Hash (SHA-256)"""
        import hashlib
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video nguồn: {video_path}")
        
        stat = os.stat(video_path)
        size = stat.st_size
        mtime = stat.st_mtime
        
        # Fast Hashing: Băm size + 1MB đầu + 1MB cuối
        chunk_size = 1024 * 1024  # 1MB
        hasher = hashlib.sha256()
        hasher.update(str(size).encode('utf-8'))
        
        try:
            with open(video_path, 'rb') as f:
                hasher.update(f.read(chunk_size))
                if size > chunk_size:
                    f.seek(-chunk_size, os.SEEK_END)
                    hasher.update(f.read(chunk_size))
        except Exception as e:
            print(f"Lỗi khi đọc file để tạo hash: {e}")
            
        fingerprint = hasher.hexdigest()
        
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
        
        self.save_project()
        return self.current_project

    def save_project(self) -> None:
        """Lưu Project hiện tại xuống đĩa cứng, chia thành các file riêng biệt"""
        if not self.current_project or not self.project_dir:
            return
            
        self.current_project.updated_at = datetime.now().isoformat()
        
        # 1. Lưu project.json
        proj_data = {
            "schema_version": self.current_project.schema_version,
            "project_id": self.current_project.project_id,
            "name": self.current_project.name,
            "created_at": self.current_project.created_at,
            "updated_at": self.current_project.updated_at,
            "source": asdict(self.current_project.source)
        }
        atomic_save_json(os.path.join(self.project_dir, "project.json"), proj_data)
        
        # 2. Lưu state.json
        state_data = {
            "timing_status": self.current_project.state.timing_status,
            "text_status": self.current_project.state.text_status,
            "export_status": self.current_project.state.export_status,
            "active_artifact_id": self.current_project.state.active_artifact_id,
            "selected_segment_id": self.current_project.state.selected_segment_id,
            "dirty": False,
            # [S7.1-T05] Lưu TimingState
            "timing": asdict(self.current_project.state.timing)
        }
        atomic_save_json(os.path.join(self.project_dir, "state.json"), state_data)
        
        # 3. Lưu workspace.json
        workspace_data = asdict(self.current_project.state.workspace)
        atomic_save_json(os.path.join(self.project_dir, "workspace.json"), workspace_data)

        # 4. Lưu Artifact Manifest
        manifest_path = os.path.join(self.project_dir, "artifacts", "manifest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        atomic_save_json(manifest_path, self.artifact_store.to_dict(self.project_dir))
        
        self.current_project.state.dirty = False

    def open_project(self, project_dir: str) -> Project:
        """Đọc và khôi phục Project từ thư mục"""
        proj_file = os.path.join(project_dir, "project.json")
        state_file = os.path.join(project_dir, "state.json")
        workspace_file = os.path.join(project_dir, "workspace.json")
        
        if not os.path.exists(proj_file):
            raise FileNotFoundError("Thư mục này không phải là một Project AI Subtitle Studio hợp lệ.")
            
        with open(proj_file, 'r', encoding='utf-8') as f:
            p_data = json.load(f)
        source_info = SourceInfo(**p_data["source"])
        
        # Source Validation
        video_path = source_info.path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video gốc tại:\n{video_path}\nVui lòng kiểm tra lại thư mục.")
            
        current_source_info = self._generate_fingerprint(video_path)
        if current_source_info.fingerprint != source_info.fingerprint:
            raise ValueError(
                f"File video gốc đã bị thay đổi hoặc ghi đè (Sai lệch mã Hash)!\n"
                f"Không thể mở dự án để bảo vệ an toàn cho dữ liệu Timing."
            )
        
        project_state = ProjectState()
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
                project_state.timing_status = s_data.get("timing_status", "EMPTY")
                project_state.text_status = s_data.get("text_status", "EMPTY")
                project_state.export_status = s_data.get("export_status", "EMPTY")
                project_state.active_artifact_id = s_data.get("active_artifact_id")
                project_state.selected_segment_id = s_data.get("selected_segment_id")
                
                # --- [S7.1-T05 & T08] Backward Compatibility cho TimingState ---
                if "timing" in s_data:
                    valid_timing_keys = {k for k in s_data["timing"].keys() if k in TimingState.__dataclass_fields__}
                    project_state.timing = TimingState(**{k: s_data["timing"][k] for k in valid_timing_keys})
                else:
                    project_state.timing = TimingState()
                # ---------------------------------------------------------------
        
        if os.path.exists(workspace_file):
            with open(workspace_file, 'r', encoding='utf-8') as f:
                w_data = json.load(f)
                valid_ws_keys = {k for k in w_data.keys() if k in WorkspaceState.__dataclass_fields__}
                project_state.workspace = WorkspaceState(**{k: w_data[k] for k in valid_ws_keys})
                
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
        
        manifest_path = os.path.join(self.project_dir, "artifacts", "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            self.artifact_store.from_dict(manifest_data, self.project_dir)
        
        return self.current_project

    def close_project(self) -> None:
        self.current_project = None
        self.project_dir = None
        self.artifact_store.clear()

    def mark_dirty(self) -> None:
        if self.current_project:
            self.current_project.state.dirty = True

    # ========================================================
    # [SPRINT 7.1] TIMING CHECKPOINT I/O
    # ========================================================
    def save_timing_checkpoint(self, checkpoint: TimingCheckpoint) -> None:
        """[S7.1-T06] Lưu cấu trúc Checkpoint xuống thư mục con của artifacts"""
        if not self.project_dir:
            return
        checkpoint_dir = os.path.join(self.project_dir, "artifacts", "timing")
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(checkpoint_dir, "checkpoint.json")
        atomic_save_json(checkpoint_path, asdict(checkpoint))

    def load_timing_checkpoint(self) -> TimingCheckpoint | None:
        """Khôi phục Checkpoint, trả về None nếu chưa tồn tại"""
        if not self.project_dir:
            return None
        checkpoint_path = os.path.join(self.project_dir, "artifacts", "timing", "checkpoint.json")
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                valid_keys = {k for k in data.keys() if k in TimingCheckpoint.__dataclass_fields__}
                return TimingCheckpoint(**{k: data[k] for k in valid_keys})
            except Exception as e:
                print(f"[ERROR] Không thể nạp Timing Checkpoint: {e}")
                return None
        return None 