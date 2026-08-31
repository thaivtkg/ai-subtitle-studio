import json
import os
from dataclasses import asdict
from typing import Optional

from core.subtitle_generation.subtitle_generation_checkpoint import (
    SubtitleGenerationCheckpoint,
)


class SubtitleGenerationCheckpointManager:
    """Atomic persistence for the resumable subtitle-generation checkpoint."""

    def __init__(self, project_service):
        self.project_service = project_service

    def _get_checkpoint_path(self) -> Optional[str]:
        project = self.project_service.current_project
        project_dir = getattr(self.project_service, "project_dir", None) or getattr(
            project, "project_dir", None
        )
        if not project or not project_dir:
            return None
        checkpoint_dir = os.path.join(
            project_dir, "artifacts", "subtitle_generation"
        )
        os.makedirs(checkpoint_dir, exist_ok=True)
        return os.path.join(checkpoint_dir, "checkpoint.json")

    def save_checkpoint(self, checkpoint: SubtitleGenerationCheckpoint) -> None:
        path = self._get_checkpoint_path()
        if not path:
            return
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(asdict(checkpoint), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def load_checkpoint(self) -> Optional[SubtitleGenerationCheckpoint]:
        path = self._get_checkpoint_path()
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            fields = SubtitleGenerationCheckpoint.__dataclass_fields__
            return SubtitleGenerationCheckpoint(
                **{key: data[key] for key in fields if key in data}
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError):
            return None
