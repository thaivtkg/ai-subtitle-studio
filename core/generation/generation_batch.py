from dataclasses import dataclass

@dataclass
class GenerationBatch:
    batch_id: str
    start_stt: int  # Đổi tên từ start_index
    end_stt: int    # Đổi tên từ end_index
    status: str     # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, STALE
    revision: int
    created_at: str
    updated_at: str