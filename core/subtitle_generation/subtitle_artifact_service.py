import json
import os
import uuid
from datetime import datetime
from typing import Optional

from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactStatus, ArtifactType


class SubtitleArtifactService:
    """Creates and atomically persists the project's canonical subtitle JSON."""

    def __init__(self, project_service):
        self.project_service = project_service

    def get_or_create_artifact(self) -> Optional[Artifact]:
        project = self.project_service.current_project
        project_dir = getattr(self.project_service, "project_dir", None) or getattr(
            project, "project_dir", None
        )
        if not project or not project_dir:
            return None

        artifact_store = self.project_service.artifact_store
        artifact_id = getattr(project.state, "subtitle_artifact_id", None)
        if artifact_id:
            artifact = artifact_store.get(artifact_id)
            if artifact:
                return artifact

        # Preserve a persisted ID when the manifest is being rebuilt.
        artifact_id = artifact_id or str(uuid.uuid4())
        now = datetime.now().isoformat()
        subtitle_dir = os.path.join(
            project_dir, "artifacts", "subtitle"
        )
        os.makedirs(subtitle_dir, exist_ok=True)
        path = os.path.join(subtitle_dir, f"{artifact_id}.sub.json")

        artifact = Artifact(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.SUBTITLE,
            path=path,
            created_at=now,
            updated_at=now,
            source_project_id=project.project_id,
            status=ArtifactStatus.READY,
            revision=0,
        )
        project.state.subtitle_artifact_id = artifact_id
        artifact_store.register(artifact)
        self._save_atomic(path, {"version": 1, "segments": []})
        mark_dirty = getattr(self.project_service, "mark_dirty", None)
        if mark_dirty:
            mark_dirty()
        return artifact

    @staticmethod
    def _save_atomic(path: str, data: dict) -> None:
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @staticmethod
    def load_data(path: str) -> dict:
        if not os.path.exists(path):
            return {"version": 1, "segments": []}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
                raise ValueError("Invalid subtitle artifact schema")
            return data
        except (OSError, ValueError, json.JSONDecodeError):
            return {"version": 1, "segments": []}
