from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Callable
from core.generation.generation_batch import GenerationBatch
from core.generation.generation_request import GenerationRequest
from core.generation.context_engine import SubtitleContextEngine
from core.generation.context_policy import ContextPolicy
from core.ai.ai_engine import AIEngine
from core.ai.ai_request import AIRequest
from core.ai.prompt_builder import PromptBuilder
from core.generation.generation_validator import GenerationValidator

class GenerationWorker(QThread):
    progress_signal = Signal(int, str)
    error_signal = Signal(str)
    # BLOCKER 3 FIXED: Phát tín hiệu thay vì chạy hàm trực tiếp
    batch_ready_signal = Signal(object, list, str) 
    finished_signal = Signal()

    def __init__(self, request: GenerationRequest, batches: List[GenerationBatch], all_segments: List[Dict], ai_engine: AIEngine, policy: ContextPolicy):
        super().__init__()
        self.request = request
        self.batches = batches
        self.all_segments = all_segments
        self.ai_engine = ai_engine
        self.policy = policy
        self.is_cancelled = False
        
        # Cổng cắm (Hook) để Service đưa hàm Commit vào
        self.commit_callback: Callable = None 

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            total_batches = len(self.batches)
            for i, batch in enumerate(self.batches):
                if self.is_cancelled:
                    self.progress_signal.emit(int((i / total_batches) * 100), "Đã hủy tiến trình an toàn.")
                    break

                if batch.status == "COMPLETED":
                    continue

                batch.status = "RUNNING"
                self.progress_signal.emit(int((i / total_batches) * 100), f"Đang xử lý Batch {i+1}/{total_batches}...")

                prev_segs, target_segs, next_segs = SubtitleContextEngine.build_context(
                    self.all_segments, batch.start_stt, batch.end_stt, self.policy
                )

                prompt = PromptBuilder.build_context_prompt(
                    prev_segs, target_segs, next_segs, 
                    "Bạn là chuyên gia dịch thuật phụ đề. Hãy dịch/điền chữ cho các khối mục tiêu."
                )

                ai_req = AIRequest(
                    request_id=self.request.request_id,
                    system_instruction="Trả về JSON chuẩn. Không giải thích.",
                    prompt=prompt,
                    temperature=self.request.temperature,
                    max_tokens=self.request.max_tokens
                )
                ai_res = self.ai_engine.generate(ai_req)

                if ai_res.error or not ai_res.parsed_json:
                    batch.status = "FAILED"
                    self.error_signal.emit(f"Batch {batch.batch_id} lỗi AI: {ai_res.error or 'Parse JSON thất bại'}")
                    break # DỪNG DÂY CHUYỀN

                try:
                    candidates = GenerationValidator.validate(
                        ai_res.parsed_json, target_segs, 
                        self.request.request_id, ai_res.request_id, self.request.model_id
                    )
                    # Gửi Signal về Main Thread để nó tự xử lý Commit
                    self.batch_ready_signal.emit(batch, candidates, ai_res.request_id)
                    # Tạm ngưng Worker chờ Main Thread commit xong (trong Service sẽ quản lý việc chạy Batch tiếp theo)
                    # Ở phiên bản MVP này, ta giả định Main Thread xử lý signal đồng bộ nhanh, 
                    # Worker sẽ tự đi tiếp. Nếu lỗi, Signal error từ Main Thread sẽ gọi self.cancel().
                except Exception as val_err:
                    batch.status = "FAILED"
                    self.error_signal.emit(f"Batch {batch.batch_id} bị từ chối: {str(val_err)}")
                    break

            if not self.is_cancelled:
                self.progress_signal.emit(100, "Hoàn tất sinh chữ!")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(f"Lỗi hệ thống ngầm: {str(e)}")