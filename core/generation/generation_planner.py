import uuid
from datetime import datetime
from typing import List
from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch

class GenerationPlanner:
    @staticmethod
    def create_plan(request: GenerationRequest, batch_size: int) -> List[GenerationBatch]:
        batches = []
        # Lấy STT từ Request (1-based)
        start = request.start_segment
        end = request.end_segment
        
        if start > end or batch_size <= 0:
            return batches

        current_start = start
        while current_start <= end:
            current_end = min(current_start + batch_size - 1, end)
            
            batch = GenerationBatch(
                batch_id=str(uuid.uuid4()),
                start_stt=current_start,  # Gán đúng tên thuộc tính
                end_stt=current_end,      # Gán đúng tên thuộc tính
                status="PENDING",
                revision=0,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            batches.append(batch)
            current_start = current_end + 1
            
        return batches