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
from workers.generation_worker import GenerationBatchWorker

class GenerationService(QObject):
    def __init__(self, ai_engine: AIEngine, project_service, data_provider):
        super().__init__()
        self.ai_engine = ai_engine
        self.project_service = project_service
        self.data_provider = data_provider
        self.checkpoint_manager = GenerationCheckpointManager(project_service)
        self.text_artifact_service = TextArtifactService(project_service, data_provider)
        
        self.policy = ContextPolicy(before=3, after=3, max_chars=6000)
        self.current_worker: Optional[GenerationBatchWorker] = None
        self.current_request: Optional[GenerationRequest] = None
        self.current_batches: List[GenerationBatch] = []
        self.current_checkpoint: Optional[GenerationCheckpoint] = None
        self.all_segments_ref: List[Dict] = []
        self._is_cancelled: bool = False
        
        self.on_progress = None
        self.on_batch_complete = None
        self.on_error = None
        self.on_finish = None

    def start_generation(self, request: GenerationRequest, all_segments: List[Dict], batch_size: int):
        project = self.project_service.current_project
        if not project: raise ValueError("Không có Project nào đang mở.")

        self._is_cancelled = False
        self.all_segments_ref = all_segments
        self.current_request = request
        self.current_batches = GenerationPlanner.create_plan(request, batch_size)
        
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)
        timing_rev = timing_artifact.revision if timing_artifact else 0

        text_artifact = self.text_artifact_service.get_or_create_text_artifact()
        text_rev = text_artifact.revision if text_artifact else 0
        source_fp = getattr(project.source, 'fingerprint', 'unknown') if hasattr(project, 'source') else 'unknown'

        self.current_checkpoint = GenerationCheckpoint(
            project_id=project.project_id,
            source_fingerprint=source_fp,
            timing_artifact_id=timing_art_id,
            text_artifact_id=text_artifact.artifact_id,
            timing_revision=timing_rev,
            text_revision=text_rev,
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
        self._dispatch_next_batch()

    def resume_generation(self, all_segments: List[Dict]):
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if not checkpoint: raise ValueError("Không tìm thấy Checkpoint.")

        project = self.project_service.current_project
        if not project: raise ValueError("Không có Project nào đang mở.")

        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)
        text_art_id = getattr(project.state, 'text_artifact_id', None)
        source_fp = getattr(project.source, 'fingerprint', 'unknown') if hasattr(project, 'source') else 'unknown'

        # IDENTITY & STALE GUARDS
        if checkpoint.project_id != project.project_id: raise ValueError("Checkpoint thuộc về Project khác.")
        if checkpoint.source_fingerprint != source_fp: raise ValueError("Source video đã thay đổi, không thể Resume.")
        if checkpoint.timing_artifact_id != timing_art_id: raise ValueError("Timing Artifact đã bị thay thế.")
        if checkpoint.text_artifact_id != text_art_id: raise ValueError("Text Artifact đã bị thay thế.")
        if not timing_artifact or timing_artifact.revision != checkpoint.timing_revision:
            raise RuntimeError("STALE TIMING: Dữ liệu Timeline đã bị thay đổi kể từ lần chạy trước.")

        completed_set = set(checkpoint.completed_batches)
        self.current_batches = []
        for b_data in checkpoint.batches_data:
            b = GenerationBatch(**b_data)
            if b.batch_id in completed_set:
                b.status = "COMPLETED"
            self.current_batches.append(b)

        self._is_cancelled = False
        self.all_segments_ref = all_segments
        self.current_request = GenerationRequest(**checkpoint.request_data)
        self.current_checkpoint = checkpoint
        self.current_checkpoint.status = "RUNNING"
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)

        self.ai_engine.load_model(self.current_request.model_id)
        self._dispatch_next_batch()

    def cancel_generation(self):
        self._is_cancelled = True
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            # Bỏ wait(1500) để không block UI. Disconnect signal thay thế.
            self.current_worker.batch_success_signal.disconnect() 
            self.current_worker.error_signal.disconnect()
            
        self.ai_engine.unload_model()
        if self.current_checkpoint:
            self.current_checkpoint.status = "CANCELLED"
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            
        if self.on_finish: 
            self.on_finish() # Kích hoạt Lifecycle kiện toàn cho UI

    def _get_next_pending_batch(self) -> Optional[GenerationBatch]:
        """Tìm batch tiếp theo chưa hoàn thành"""
        for batch in self.current_batches:
            if batch.status != "COMPLETED":
                return batch
        return None

    def _dispatch_next_batch(self):
        if self._is_cancelled: return

        next_batch = self._get_next_pending_batch()
        if not next_batch:
            if self.current_checkpoint:
                self.current_checkpoint.status = "COMPLETED"
                self.current_checkpoint.active_batch = None
                self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            self.ai_engine.unload_model()
            if self.on_progress: self.on_progress(100, "Hoàn tất sinh chữ!")
            if self.on_finish: self.on_finish()
            return

        total_batches = len(self.current_batches)
        completed_count = len(self.current_checkpoint.completed_batches)
        progress_pct = int((completed_count / total_batches) * 100) if total_batches > 0 else 0
        
        # Cập nhật Active Batch vào Checkpoint
        self.current_checkpoint.active_batch = next_batch.__dict__
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
        
        if self.on_progress:
            self.on_progress(progress_pct, f"Đang xử lý Batch {completed_count + 1}/{total_batches}...")

        self.current_worker = GenerationBatchWorker(
            self.current_request, next_batch, self.all_segments_ref, self.ai_engine, self.policy
        )
        self.current_worker.batch_success_signal.connect(self._sync_commit_batch_slot)
        self.current_worker.error_signal.connect(self._handle_worker_error)
        self.current_worker.start()

    @Slot(object, list, str)
    def _sync_commit_batch_slot(self, batch: GenerationBatch, candidates: list, res_req_id: str):
        try:
            self.text_artifact_service.commit_candidates(candidates, self.current_checkpoint)
            
            batch.status = "COMPLETED"
            if batch.batch_id not in self.current_checkpoint.completed_batches:
                self.current_checkpoint.completed_batches.append(batch.batch_id)
                
            # Cập nhật Tịnh tiến State Checkpoint
            text_art = self.project_service.artifact_store.get(self.current_checkpoint.text_artifact_id)
            if text_art: self.current_checkpoint.text_revision = text_art.revision
            
            self.current_checkpoint.next_segment_index = batch.end_stt + 1
            self.current_checkpoint.active_batch = None
            self.current_checkpoint.batches_data = [b.__dict__ for b in self.current_batches]
            self.current_checkpoint.updated_at = datetime.now().isoformat()
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            
            if self.on_batch_complete: self.on_batch_complete(batch, candidates)
            self._dispatch_next_batch()
                
        except Exception as e:
            batch.status = "STALE" if "STALE" in str(e) else "FAILED"
            if self.on_error: self.on_error(str(e))
            self.cancel_generation()

    @Slot(str)
    def _handle_worker_error(self, err_msg: str):
        if self.on_error:
            self.on_error(err_msg)
        self.cancel_generation()