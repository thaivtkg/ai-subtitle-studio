import os
from typing import Dict, List, Optional

from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactStatus, ArtifactType


class ArtifactStore:
    def __init__(self):
        self._artifacts: Dict[str, Artifact] = {}

    def register(self, artifact: Artifact) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    def get(self, artifact_id: str) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)

    def get_all(self) -> List[Artifact]:
        return list(self._artifacts.values())

    def clear(self) -> None:
        self._artifacts.clear()

    def to_dict(self, project_dir: str) -> dict:
        """Xuất danh sách Artifacts, ép đường dẫn thành Relative Path"""
        manifest = {"artifacts": []}
        for art in self.get_all():
            # Cắt đường dẫn tuyệt đối thành tương đối so với project_dir
            rel_path = os.path.relpath(art.path, project_dir) if os.path.isabs(art.path) else art.path
            art_dict = {
                "artifact_id": art.artifact_id,
                "artifact_type": art.artifact_type.name,
                "path": rel_path.replace("\\", "/"),
                "created_at": art.created_at,
                "updated_at": art.updated_at,
                "source_project_id": art.source_project_id,
                "status": art.status.name,
                "revision": art.revision,  # [S7-FINAL-FIX] Bổ sung lưu revision
                "metadata": art.metadata
            }
            manifest["artifacts"].append(art_dict)
        return manifest

    def from_dict(self, data: dict, project_dir: str) -> None:
        """Nạp danh sách Artifacts, khôi phục Relative Path và Validation"""
        self.clear()
        for item in data.get("artifacts", []):
            try:
                # Khôi phục thành đường dẫn tuyệt đối
                abs_path = os.path.normpath(os.path.join(project_dir, item["path"]))
                
                # [S7-FINAL-FIX] Validate Enum và khôi phục Revision
                artifact = Artifact(
                    artifact_id=item["artifact_id"],
                    artifact_type=ArtifactType[item["artifact_type"]],
                    path=abs_path,
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    source_project_id=item["source_project_id"],
                    status=ArtifactStatus[item["status"]],
                    revision=item.get("revision", 1), # Khôi phục revision, mặc định là 1 nếu file cũ chưa có
                    metadata=item.get("metadata", {})
                )
                self.register(artifact)
            except KeyError as e:
                # Bắt lỗi nếu file manifest bị can thiệp tay hoặc sai Enum
                print(f"[WARN] Bỏ qua Artifact '{item.get('artifact_id')}' do dữ liệu hỏng hoặc Enum không hợp lệ: Thiếu key {e}")
            except Exception as e:
                print(f"[ERROR] Không thể nạp Artifact '{item.get('artifact_id')}': {str(e)}")