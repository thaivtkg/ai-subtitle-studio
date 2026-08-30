import uuid
from datetime import datetime
from typing import List
from core.generation.generation_request import GenerationRequest
from core.generation.generation_batch import GenerationBatch

class GenerationPlanner:
    @staticmethod
    def create_plan(request: GenerationRequest, batch_size: int) -> List[GenerationBatch]:
        """
        Nhận vào Request (vd: Dịch từ câu 21->60) và Batch Size (vd: 10).
        Sinh ra kế hoạch gồm 4 Batch: [21-30], [31-40], [41-50], [51-60].
        """
        batches = []
        start = request.start_segment
        end = request.end_segment
        
        if start > end or batch_size <= 0:
            return batches

        current_start = start
        while current_start <= end:
            # Chốt đuôi của Batch hiện tại (không vượt quá đuôi tổng)
            current_end = min(current_start + batch_size - 1, end)
            
            batch = GenerationBatch(
                batch_id=str(uuid.uuid4()),
                start_index=current_start,
                end_index=current_end,
                status="PENDING",
                revision=0,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            batches.append(batch)
            
            # Tịnh tiến con trỏ cho Batch tiếp theo
            current_start = current_end + 1
            
        return batches