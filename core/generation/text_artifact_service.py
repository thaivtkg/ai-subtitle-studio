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

    def get_or_create_text_artifact(self) -> Artifact:
        project = self.project_service.current_project
        if not project: return None
        
        art_id = getattr(project.state, 'text_artifact_id', None)
        if not art_id:
            art_id = str(uuid.uuid4())
            project.state.text_artifact_id = art_id
            
            text_dir = os.path.join(project.project_dir, "artifacts", "text")
            os.makedirs(text_dir, exist_ok=True)
            path = os.path.join(text_dir, f"{art_id}_text.json")
            
            artifact = Artifact(
                artifact_id=art_id,
                # FIXED: Dùng đúng Semantic thay vì DRAFT
                artifact_type=ArtifactType.TEXT, 
                path=path,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source_project_id=project.project_id,
                status=ArtifactStatus.READY
            )
            artifact.revision = 0
            
            self.project_service.artifact_store.register(artifact)
            self._save_text_data_atomic(path, {"version": 1.0, "segments": []})
            
        return self.project_service.artifact_store.get(art_id)
    
    def _save_text_data_atomic(self, path: str, data: dict):
        # MAJOR 10 FIXED: Atomic Text Artifact write
        temp_path = path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, path)

    def _load_text_data(self, path: str) -> dict:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": 1.0, "segments": []}

    def commit_candidates(self, candidates: List[GenerationCandidate], checkpoint: GenerationCheckpoint) -> bool:
        project = self.project_service.current_project
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)

        if not timing_artifact or timing_artifact.revision != checkpoint.timing_revision:
            raise RuntimeError("STALE_TIMING: Dữ liệu Timeline đã bị thay đổi.")

        text_artifact = self.get_or_create_text_artifact()
        
        # FIXED: Lớp khiên bảo vệ tuyệt đối cho Text Artifact
        if text_artifact.artifact_id != checkpoint.text_artifact_id:
            raise RuntimeError("STALE_TEXT_ARTIFACT: Text Artifact đã bị thay thế.")
        if text_artifact.revision != checkpoint.text_revision:
            raise RuntimeError("STALE_TEXT: Text Artifact đã bị thay đổi kể từ khi Generation bắt đầu.")

        text_data = self._load_text_data(text_artifact.path)
        existing_segs = {str(s.get('id')): s for s in text_data.get('segments', [])}
        
        for cand in candidates:
            if cand.validation_status == "PASSED":
                existing_segs[cand.segment_id] = {
                    "id": cand.segment_id,
                    "text": cand.generated_text,
                    "status": "draft"
                }
                if self.data_provider:
                    seg = self.data_provider.get_segment(cand.segment_id)
                    if seg:
                        seg.text = cand.generated_text
                        seg.status = "draft"
                    
        text_data['segments'] = list(existing_segs.values())
        
        self._save_text_data_atomic(text_artifact.path, text_data)
        text_artifact.revision += 1
        text_artifact.updated_at = datetime.now().isoformat()
        
        self.project_service.mark_dirty()
        return True