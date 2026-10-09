from enum import Enum

class GenerationErrorCode(Enum):
    # Validation errors
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RANGE_CONFLICT = "RANGE_CONFLICT"
    
    # Runtime failures
    PROJECT_MISMATCH = "PROJECT_MISMATCH"
    FINGERPRINT_MISMATCH = "FINGERPRINT_MISMATCH"
    GENERATION_RUNNING = "GENERATION_RUNNING"
    CANCELLATION = "CANCELLATION"
    WORKER_FAILURE = "WORKER_FAILURE"
    ARTIFACT_WRITE_FAILURE = "ARTIFACT_WRITE_FAILURE"
    STALE_RANGE_CONFLICT = "STALE_RANGE_CONFLICT"
    RECONCILIATION_UNSAFE = "RECONCILIATION_UNSAFE"
    STALE_SUBTITLE = "STALE_SUBTITLE"

class GenerationError(RuntimeError):
    def __init__(self, code: GenerationErrorCode, message: str):
        super().__init__(f"[{code.name}] {message}")
        self.code = code
        self.message = message
