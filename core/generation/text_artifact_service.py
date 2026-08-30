import os
import json
import uuid
from datetime import datetime
from typing import List
from core.generation.generation_candidate import GenerationCandidate
from core.generation.generation_checkpoint import GenerationCheckpoint
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus

class TextArtifactService:
    def __init__(self, project_service, data_provider):
        self.project_service = project_service
        self.data_provider = data_provider

    def _get_text_artifact(self):
        project = self.project_service.current_project
        if not project: return None
        
        art_id = getattr(project.state, 'text_artifact_id', None)
        if not art_id:
            art_id = str(uuid.uuid4())
            project.state.text_artifact_id = art_id
            
            text_dir = os.path.join(project.project_dir, "artifacts", "text")
            os.makedirs(text_dir, exist_ok=True)
            path = os.path.join(text_dir, "text_draft.json")
            
            artifact = Artifact(
                artifact_id=art_id,
                artifact_type=ArtifactType.DRAFT,
                path=path,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source_project_id=project.project_id,
                status=ArtifactStatus.READY
            )
            self.project_service.artifact_store.register(artifact)
            self._save_text_data(path, {"version": 1.0, "segments": []})
            
        return self.project_service.artifact_store.get(art_id)

    def _save_text_data(self, path: str, data: dict):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def _load_text_data(self, path: str) -> dict:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": 1.0, "segments": []}

    def commit_candidates(self, candidates: List[GenerationCandidate], checkpoint: GenerationCheckpoint) -> bool:
        project = self.project_service.current_project
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)

        # STALE GUARD: Block rác
        if not timing_artifact or timing_artifact.revision != checkpoint.generation_revision:
            raise RuntimeError("STALE_TIMING: Dữ liệu Timeline đã bị user thay đổi.")

        # LƯU XUỐNG TEXT ARTIFACT
        text_artifact = self._get_text_artifact()
        text_data = self._load_text_data(text_artifact.path)
        existing_segs = {str(s.get('id')): s for s in text_data.get('segments', [])}
        
        for cand in candidates:
            if cand.validation_status == "PASSED":
                existing_segs[cand.segment_id] = {
                    "id": cand.segment_id,
                    "text": cand.generated_text,
                    "status": "draft"  # BLOCKER FIXED: lowercase chuẩn contract
                }
                # Adapter tạm thời cho MVP: Sync lên Runtime cho User thấy chữ
                seg = self.data_provider.get_segment(cand.segment_id)
                if seg:
                    seg.text = cand.generated_text
                    seg.status = "draft"
                    
        text_data['segments'] = list(existing_segs.values())
        self._save_text_data(text_artifact.path, text_data)
        
        text_artifact.revision += 1
        text_artifact.updated_at = datetime.now().isoformat()
        
        self.project_service.mark_dirty()
        return True