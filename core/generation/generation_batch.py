from dataclasses import dataclass

@dataclass
class GenerationBatch:
    batch_id: str
    start_index: int
    end_index: int
    status: str # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, STALE
    revision: int
    created_at: str
    updated_at: str