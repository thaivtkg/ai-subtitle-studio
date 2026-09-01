from dataclasses import dataclass
from enum import Enum, auto
from core.subtitle_validation.validation_policy import ValidationMode


class Severity(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class ValidationIssue:
    segment_index: int
    severity: Severity
    code: str
    message: str
