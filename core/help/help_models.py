from dataclasses import dataclass
from enum import Enum


class GuideStartStatus(str, Enum):
    NEW = "NEW"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"
    UPDATED = "UPDATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GuideStartResult:
    status: GuideStartStatus
    status_label: str
    action_label: str


@dataclass(frozen=True)
class GuideCardViewModel:
    guide_id: str
    title: str
    description: str
    category: str
    estimated_minutes: int
    step_count: int
    start: GuideStartResult
