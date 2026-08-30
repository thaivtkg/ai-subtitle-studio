from typing import List, Dict, Optional
from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_planner import GenerationPlanner
from core.generation.context_policy import ContextPolicy
from workers.generation_worker import GenerationWorker
from core.ai.ai_engine import AIEngine

class GenerationService:
    def __init__(self, ai_engine: AIEngine):
        self.ai_engine = ai_engine
        self.current_worker: Optional[GenerationWorker] = None
        self.current_request: Optional[GenerationRequest] = None
        self.current_batches: List[GenerationBatch] = []
        self.policy = ContextPolicy(before=3, after=3, max_chars=6000)
        
        # Signal callbacks (Sẽ được UI bind vào sau)
        self.on_progress = None
        self.on_batch_complete = None
        self.on_error = None
        self.on_finish = None

    def start_generation(self, request: GenerationRequest, all_segments: List[Dict], batch_size: int):
        self.current_request = request
        self.current_batches = GenerationPlanner.create_plan(request, batch_size)
        
        self.ai_engine.load_model(request.model_id)
        self._run_worker(all_segments)

    def resume_generation(self, all_segments: List[Dict]):
        if not self.current_batches or not self.current_request:
            raise ValueError("Không có tiến trình nào để Resume.")
        self._run_worker(all_segments)

    def cancel_generation(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()

    def _run_worker(self, all_segments: List[Dict]):
        if self.current_worker and self.current_worker.isRunning():
            return
            
        self.current_worker = GenerationWorker(
            self.current_request, 
            self.current_batches, 
            all_segments, 
            self.ai_engine, 
            self.policy
        )
        
        if self.on_progress: self.current_worker.progress_signal.connect(self.on_progress)
        if self.on_error: self.current_worker.error_signal.connect(self.on_error)
        if self.on_finish: self.current_worker.finished_signal.connect(self.on_finish)
        
        # Móc nối callback xử lý Batch
        self.current_worker.batch_completed_signal.connect(self._handle_batch_completed)
        self.current_worker.start()

    def _handle_batch_completed(self, batch: GenerationBatch, candidates: list):
        try:
            # Nếu TextArtifactService từ chối (bắn exception STALE_TIMING), tiến trình sẽ nhảy ngay xuống block except.
            # Lưu ý: Khi đấu nối UI (PR 9.6), chúng ta sẽ truyền text_artifact_service và checkpoint thật vào đây.
            if hasattr(self, 'text_artifact_service') and hasattr(self, 'current_checkpoint'):
                self.text_artifact_service.commit_candidates(candidates, self.current_checkpoint)
                
                # Cập nhật Checkpoint đánh dấu Batch này đã xong
                self.current_checkpoint.completed_batches.append(batch.batch_id)
                if hasattr(self, 'checkpoint_manager'):
                    self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
                    
            if self.on_batch_complete:
                self.on_batch_complete(batch, candidates)
                
        except Exception as e:
            batch.status = "STALE" if "STALE" in str(e) else "FAILED"
            if self.on_error:
                self.on_error(str(e))
            self.cancel_generation() # Dừng dây chuyền lập tức nếu phát hiện bất đồng bộ