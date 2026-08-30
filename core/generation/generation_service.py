from datetime import datetime
from typing import List, Dict, Optional
from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_planner import GenerationPlanner
from core.generation.context_policy import ContextPolicy
from core.generation.generation_checkpoint import GenerationCheckpoint
from core.generation.generation_checkpoint_manager import GenerationCheckpointManager
from core.generation.text_artifact_service import TextArtifactService
from core.ai.ai_engine import AIEngine
from workers.generation_worker import GenerationWorker

class GenerationService:
    def __init__(self, ai_engine: AIEngine, project_service, data_provider):
        self.ai_engine = ai_engine
        self.project_service = project_service
        self.checkpoint_manager = GenerationCheckpointManager(project_service)
        self.text_artifact_service = TextArtifactService(project_service, data_provider)
        
        self.policy = ContextPolicy(before=3, after=3, max_chars=6000)
        
        self.current_worker: Optional[GenerationWorker] = None
        self.current_request: Optional[GenerationRequest] = None
        self.current_batches: List[GenerationBatch] = []
        self.current_checkpoint: Optional[GenerationCheckpoint] = None
        
        # Event callbacks
        self.on_progress = None
        self.on_batch_complete = None
        self.on_error = None
        self.on_finish = None

    def start_generation(self, request: GenerationRequest, all_segments: List[Dict], batch_size: int):
        project = self.project_service.current_project
        if not project:
            raise ValueError("Không có Project nào đang mở.")

        self.current_request = request
        self.current_batches = GenerationPlanner.create_plan(request, batch_size)
        
        # Lấy Revision hiện tại của Timeline
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)
        timing_rev = timing_artifact.revision if timing_artifact else 0

        # Khởi tạo Checkpoint mới
        self.current_checkpoint = GenerationCheckpoint(
            project_id=project.project_id,
            source_fingerprint=getattr(project.state, 'source_fingerprint', 'unknown'),
            timing_artifact_id=timing_art_id,
            text_artifact_id="",
            request_id=request.request_id,
            generation_revision=timing_rev,
            next_segment_index=request.start_segment,
            completed_batches=[],
            active_batch=None,
            updated_at=datetime.now().isoformat()
        )
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)

        self.ai_engine.load_model(request.model_id)
        self._run_worker(all_segments)

    def resume_generation(self, all_segments: List[Dict]):
        """Khôi phục quy trình điền chữ nếu bị gián đoạn"""
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if not checkpoint:
            raise ValueError("Không tìm thấy Checkpoint để khôi phục.")

        project = self.project_service.current_project
        timing_art_id = getattr(project.state.timing, 'timing_artifact_id', None) if hasattr(project.state, 'timing') else project.state.active_artifact_id
        timing_artifact = self.project_service.artifact_store.get(timing_art_id)

        # STALE GUARD: Chặn ngay từ cửa nếu Timeline đã bị thay đổi
        if not timing_artifact or timing_artifact.revision != checkpoint.generation_revision:
            raise RuntimeError("STALE TIMING: Dữ liệu Timeline đã bị thay đổi kể từ lần chạy trước. Không thể tiếp tục!")

        if not self.current_batches or not self.current_request:
            raise ValueError("Chưa có thông tin Session trong RAM. Tính năng Resume App Reboot sẽ được mở rộng ở phiên bản sau.")

        self.current_checkpoint = checkpoint
        self.ai_engine.load_model(self.current_request.model_id)
        self._run_worker(all_segments)

    def cancel_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.wait(1500) # Đợi luồng ngầm dừng hẳn
        self.ai_engine.unload_model() # Lập tức xả VRAM/RAM

    def _run_worker(self, all_segments: List[Dict]):
        self.current_worker = GenerationWorker(
            self.current_request, 
            self.current_batches, 
            all_segments, 
            self.ai_engine, 
            self.policy
        )
        
        # Bơm Callback đồng bộ
        self.current_worker.commit_callback = self._sync_commit_batch
        
        if self.on_progress: self.current_worker.progress_signal.connect(self.on_progress)
        if self.on_error: self.current_worker.error_signal.connect(self.on_error)
        
        # Lắng nghe Signal hoàn tất để tự động dọn RAM
        self.current_worker.finished_signal.connect(self._handle_finished)
        self.current_worker.start()

    def _sync_commit_batch(self, batch: GenerationBatch, candidates: list):
        """Hàm này được Worker gọi khi AI trả kết quả. Nó chạy đồng bộ để chặn luồng."""
        # 1. Ghi xuống Text Artifact (Có cơ chế kiểm tra Revision chống STALE)
        self.text_artifact_service.commit_candidates(candidates, self.current_checkpoint)
        
        # 2. Cập nhật Checkpoint an toàn
        self.current_checkpoint.completed_batches.append(batch.batch_id)
        self.current_checkpoint.updated_at = datetime.now().isoformat()
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
        
        if self.on_batch_complete:
            self.on_batch_complete(batch, candidates)

    def _handle_finished(self):
        self.ai_engine.unload_model()
        if self.on_finish:
            self.on_finish()