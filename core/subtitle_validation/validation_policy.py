from enum import Enum, auto


class ValidationMode(Enum):
    TIMING_DRAFT = auto()
    FULL_SUBTITLE = auto()


class ValidationPolicy:
    """Ngưỡng cấu hình cho quá trình kiểm duyệt phụ đề."""

    MIN_DURATION_MS = 500
    MAX_DURATION_MS = 7000
    MAX_CPS = 20.0
