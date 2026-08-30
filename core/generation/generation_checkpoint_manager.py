import os
import json
from core.generation.generation_checkpoint import GenerationCheckpoint

class GenerationCheckpointManager:
    def __init__(self, project_service):
        self.project_service = project_service

    def _get_checkpoint_path(self):
        project = self.project_service.current_project
        if not project:
            return None
        gen_dir = os.path.join(project.project_dir, "artifacts", "generation")
        os.makedirs(gen_dir, exist_ok=True)
        return os.path.join(gen_dir, "checkpoint.json")

    def save_checkpoint(self, checkpoint: GenerationCheckpoint):
        path = self._get_checkpoint_path()
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.__dict__, f, ensure_ascii=False, indent=4)

    def load_checkpoint(self) -> GenerationCheckpoint:
        path = self._get_checkpoint_path()
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return GenerationCheckpoint(**data)
            except Exception:
                pass
        return None