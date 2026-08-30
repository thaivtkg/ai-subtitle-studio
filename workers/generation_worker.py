from PySide6.QtCore import QThread, Signal
from typing import List, Dict
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
    batch_completed_signal = Signal(object, list) # Truyền về (GenerationBatch, List[GenerationCandidate])
    error_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, request: GenerationRequest, batches: List[GenerationBatch], all_segments: List[Dict], ai_engine: AIEngine, policy: ContextPolicy):
        super().__init__()
        self.request = request
        self.batches = batches
        self.all_segments = all_segments
        self.ai_engine = ai_engine
        self.policy = policy
        self.is_cancelled = False

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

                # 1. Bơm Context
                prev_segs, target_segs, next_segs = SubtitleContextEngine.build_context(
                    self.all_segments, batch.start_index, batch.end_index, self.policy
                )

                # 2. Xây Prompt
                instruction = "Điền chữ / Dịch thuật ngữ cảnh cho các khối phụ đề sau."
                prompt = PromptBuilder.build_context_prompt(prev_segs, target_segs, next_segs, instruction)

                # 3. Gửi AI
                ai_req = AIRequest(
                    request_id=self.request.request_id,
                    system_instruction="You are a professional subtitle translator.",
                    prompt=prompt,
                    temperature=self.request.temperature,
                    max_tokens=self.request.max_tokens
                )
                ai_res = self.ai_engine.generate(ai_req)

                if ai_res.error or not ai_res.parsed_json:
                    batch.status = "FAILED"
                    self.error_signal.emit(f"Batch {batch.batch_id} lỗi: {ai_res.error or 'Parse JSON thất bại'}")
                    continue

                # 4. Kiểm duyệt dữ liệu Output
                candidates = GenerationValidator.validate(ai_res.parsed_json, target_segs, self.request.request_id, self.request.model_id)

                if any(c.validation_status == "FAILED" for c in candidates):
                    batch.status = "FAILED"
                    self.error_signal.emit(f"Batch {batch.batch_id} bị từ chối do thiếu/sai dữ liệu Validation.")
                else:
                    batch.status = "COMPLETED"

                # Gửi Candidates về cho Service xử lý tiếp
                self.batch_completed_signal.emit(batch, candidates)

            if not self.is_cancelled:
                self.progress_signal.emit(100, "Hoàn tất sinh chữ!")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(str(e))