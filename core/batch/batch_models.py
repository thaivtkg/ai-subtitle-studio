from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Optional

class BatchStatus(Enum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    TRANSLATING = "TRANSLATING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class BatchJob:
    id: str
    input_file: str
    status: BatchStatus = BatchStatus.PENDING
    progress: float = 0.0
    error_message: Optional[str] = None
    output_path: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'BatchJob':
        data = data.copy()
        if 'status' in data:
            data['status'] = BatchStatus(data['status'])
        return cls(**data)

@dataclass
class BatchSession:
    session_id: str
    model_size: str
    target_lang: str
    output_format: str
    jobs: List[BatchJob] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data['jobs'] = [job.to_dict() for job in self.jobs]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'BatchSession':
        data = data.copy()
        if 'jobs' in data:
            data['jobs'] = [BatchJob.from_dict(job_data) for job_data in data['jobs']]
        return cls(**data)
