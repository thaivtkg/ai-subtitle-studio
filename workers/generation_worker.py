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

class GenerationBatchWorker(QThread):
    batch_success_signal = Signal(object, list, str)
    error_signal = Signal(str)

    def __init__(self, request: GenerationRequest, batch: GenerationBatch, all_segments: List[Dict], ai_engine: AIEngine, policy: ContextPolicy):
        super().__init__()
        self.request = request
        self.batch = batch
        self.all_segments = all_segments
        self.ai_engine = ai_engine
        self.policy = policy
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            if self.is_cancelled:
                return

            self.batch.status = "RUNNING"

            prev_segs, target_segs, next_segs = SubtitleContextEngine.build_context(
                self.all_segments, self.batch.start_stt, self.batch.end_stt, self.policy
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

            if self.is_cancelled:
                return

            ai_res = self.ai_engine.generate(ai_req)

            if self.is_cancelled:
                return

            if ai_res.error or not ai_res.parsed_json:
                self.batch.status = "FAILED"
                self.error_signal.emit(f"Batch {self.batch.batch_id} lỗi AI: {ai_res.error or 'Parse JSON thất bại'}")
                return

            candidates = GenerationValidator.validate(
                ai_res.parsed_json, target_segs, 
                self.request.request_id, ai_res.request_id, self.request.model_id
            )
            
            self.batch_success_signal.emit(self.batch, candidates, ai_res.request_id)

        except Exception as e:
            self.batch.status = "FAILED"
            self.error_signal.emit(f"Lỗi xử lý Batch {self.batch.batch_id}: {str(e)}")