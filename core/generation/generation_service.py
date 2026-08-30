import json
from datetime import datetime
from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Slot
from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_planner import GenerationPlanner
from core.generation.context_policy import ContextPolicy
from core.generation.generation_checkpoint import GenerationCheckpoint
from core.generation.generation_checkpoint_manager import GenerationCheckpointManager
from core.generation.text_artifact_service import TextArtifactService
from core.ai.ai_engine import AIEngine
from workers.generation_worker import GenerationWorker

class GenerationService(QObject):
    def __init__(self, ai_engine: AIEngine, project_service, data_provider):
        super().__init__()
        self.ai_engine = ai_engine
        self.project_service = project_service
        self.data_provider = data_provider # Lưu lại để update UI sau khi commit
        self.checkpoint_manager = GenerationCheckpointManager(project_service)
        self.text_artifact_service = TextArtifactService(project_service, data_provider)
        
        self.policy = ContextPolicy(before=3, after=3, max_chars=6000)
        self.current_worker: Optional[GenerationWorker] = None
        self.current_request: Optional[GenerationRequest] = None
        self.current_batches: List[GenerationBatch] = []
        self.current_checkpoint: Optional[GenerationCheckpoint] = None
        
        self.on_progress = None
        self.on_batch_complete = None
        self.on_error = None
        self.on_finish = None

    def start_generation(self, request: GenerationRequest, all_segments: List[Dict], batch_size: int):
        project = self.project_service.current_project
        if not project: raise ValueError("Không có Project nào đang mở.")

        self.current_request = request
        self.current_batches = GenerationPlanner.create_plan(request, batch_size)
        
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)
        timing_rev = timing_artifact.revision if timing_artifact else 0

        # BLOCKER 4 FIXED: Tạo Text Artifact trước, lấy ID nhét vào Checkpoint
        text_artifact = self.text_artifact_service.get_or_create_text_artifact()
        source_fp = getattr(project.source, 'fingerprint', 'unknown') if hasattr(project, 'source') else 'unknown' # BLOCKER 6 FIXED

        self.current_checkpoint = GenerationCheckpoint(
            project_id=project.project_id,
            source_fingerprint=source_fp,
            timing_artifact_id=timing_art_id,
            text_artifact_id=text_artifact.artifact_id,
            request_id=request.request_id,
            generation_revision=timing_rev,
            next_segment_index=request.start_segment,
            completed_batches=[],
            request_data=request.__dict__,
            batches_data=[b.__dict__ for b in self.current_batches],
            active_batch=None,
            updated_at=datetime.now().isoformat(),
            status="RUNNING"
        )
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
        self.ai_engine.load_model(request.model_id)
        self._run_worker(all_segments)

    def resume_generation(self, all_segments: List[Dict]):
        # BLOCKER 5 & 7 FIXED: True Resume với Deep Validation
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if not checkpoint: raise ValueError("Không tìm thấy Checkpoint.")

        project = self.project_service.current_project
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)
        source_fp = getattr(project.source, 'fingerprint', 'unknown') if hasattr(project, 'source') else 'unknown'

        if checkpoint.project_id != project.project_id: raise ValueError("Checkpoint thuộc về Project khác.")
        if checkpoint.source_fingerprint != source_fp: raise ValueError("Source video đã thay đổi, không thể Resume.")
        if checkpoint.timing_artifact_id != timing_art_id: raise ValueError("Timing Artifact đã bị thay thế.")
        if not timing_artifact or timing_artifact.revision != checkpoint.generation_revision:
            raise RuntimeError("STALE TIMING: Dữ liệu Timeline đã bị thay đổi kể từ lần chạy trước.")

        # Phục hồi State lên RAM
        self.current_request = GenerationRequest(**checkpoint.request_data)
        self.current_batches = [GenerationBatch(**b_data) for b_data in checkpoint.batches_data]
        self.current_checkpoint = checkpoint
        self.current_checkpoint.status = "RUNNING"
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)

        self.ai_engine.load_model(self.current_request.model_id)
        self._run_worker(all_segments)

    def cancel_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(1500)
        self.ai_engine.unload_model()
        if self.current_checkpoint:
            self.current_checkpoint.status = "CANCELLED"
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)

    def _run_worker(self, all_segments: List[Dict]):
        self.current_worker = GenerationWorker(
            self.current_request, self.current_batches, all_segments, self.ai_engine, self.policy
        )
        
        # KẾT NỐI SIGNAL ĐẾN MAIN THREAD SLOT
        self.current_worker.batch_ready_signal.connect(self._sync_commit_batch_slot)
        
        if self.on_progress: self.current_worker.progress_signal.connect(self.on_progress)
        if self.on_error: self.current_worker.error_signal.connect(self.on_error)
        self.current_worker.finished_signal.connect(self._handle_finished)
        self.current_worker.start()

    @Slot(object, list, str)
    def _sync_commit_batch_slot(self, batch: GenerationBatch, candidates: list, res_req_id: str):
        """Chạy trên Main Thread, thao tác File và UI an toàn"""
        try:
            # Ghi Text Artifact và đồng bộ DataProvider cùng lúc
            self.text_artifact_service.commit_candidates(candidates, self.current_checkpoint)
            
            batch.status = "COMPLETED"
            self.current_checkpoint.completed_batches.append(batch.batch_id)
            self.current_checkpoint.updated_at = datetime.now().isoformat()
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            
            if self.on_batch_complete:
                self.on_batch_complete(batch, candidates)
                
        except Exception as e:
            batch.status = "STALE" if "STALE" in str(e) else "FAILED"
            if self.on_error: self.on_error(str(e))
            self.cancel_generation()