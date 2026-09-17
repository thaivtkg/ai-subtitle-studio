from dataclasses import dataclass
from enum import Enum, auto



class ValidationMode(Enum):
    TIMING_DRAFT = auto()
    FULL_SUBTITLE = auto()


class ValidationPolicy:
    """Ngưỡng cấu hình cho quá trình kiểm duyệt phụ đề."""

    MIN_DURATION_MS = 500
    MAX_DURATION_MS = 7000
    MAX_CPS = 20.0


@dataclass(frozen=True)
class ValidationProfile:
    """Optional thresholds for callers that need a different validation view."""

    min_duration_ms: int = ValidationPolicy.MIN_DURATION_MS
    max_duration_ms: int = ValidationPolicy.MAX_DURATION_MS
    max_cps: float = ValidationPolicy.MAX_CPS
    max_chars_per_line: int | None = None
    max_lines: int | None = None
    small_gap_ms: int | None = None
    overlap_severity: object = None
    report_overlap_on_both_segments: bool = True
    count_newlines_in_cps: bool = True
