from typing import Dict, List, Optional
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus

class ArtifactStore:
    """Kho lưu trữ In-Memory quản lý vòng đời của mọi Artifact trong Project"""
    def __init__(self):
        self._artifacts: Dict[str, Artifact] = {}

    def register(self, artifact: Artifact) -> None:
        """Đăng ký một Artifact mới vào hệ thống"""
        self._artifacts[artifact.artifact_id] = artifact

    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Lấy Artifact theo ID"""
        return self._artifacts.get(artifact_id)

    def list_by_type(self, artifact_type: ArtifactType) -> List[Artifact]:
        """Lấy danh sách toàn bộ Artifact thuộc một loại cụ thể"""
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def update(self, artifact: Artifact) -> None:
        """Cập nhật trạng thái/metadata của một Artifact"""
        if artifact.artifact_id in self._artifacts:
            self._artifacts[artifact.artifact_id] = artifact
        else:
            raise ValueError(f"Artifact {artifact.artifact_id} không tồn tại trong hệ thống.")

    def remove(self, artifact_id: str) -> None:
        """Xóa Artifact khỏi bộ nhớ (Chưa xóa file cứng)"""
        if artifact_id in self._artifacts:
            del self._artifacts[artifact_id]

    def mark_stale_by_type(self, artifact_type: ArtifactType) -> None:
        """
        Đánh dấu toàn bộ Artifact thuộc một loại là STALE (Lỗi thời).
        Ví dụ: Khi sửa Timing, toàn bộ Draft cũ phải bị gán nhãn STALE.
        """
        for artifact in self.list_by_type(artifact_type):
            if artifact.status in (ArtifactStatus.PENDING, ArtifactStatus.READY, ArtifactStatus.RUNNING):
                artifact.status = ArtifactStatus.STALE

    def get_all(self) -> List[Artifact]:
        """Lấy toàn bộ Artifact để phục vụ việc Save Project xuống JSON"""
        return list(self._artifacts.values())
        
    def clear(self) -> None:
        """Xóa trắng kho khi đóng Project"""
        self._artifacts.clear()