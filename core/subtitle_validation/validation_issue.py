from dataclasses import dataclass
from enum import Enum, auto


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
