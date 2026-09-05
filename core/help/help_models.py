from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GuideStartStatus(str, Enum):
    READY = "READY"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    START_FAILED = "START_FAILED"


class SearchResultType(str, Enum):
    GUIDE = "GUIDE"
    SHORTCUT = "SHORTCUT"


@dataclass(frozen=True)
class GuideStartResult:
    status: GuideStartStatus
    guide_id: str
    reason: Optional[str] = None


@dataclass(frozen=True)
class GuideCardViewModel:
    guide_id: str
    title: str
    description: str
    category: str
    estimated_minutes: int
    badge: str
    cta: str
    enabled: bool = True
    blocked_reason: Optional[str] = None


@dataclass(frozen=True)
class RuntimeShortcutDescriptor:
    action_id: str
    label: str
    sequence: str
    context: str = "Global"


@dataclass(frozen=True)
class HelpSearchResult:
    result_type: SearchResultType
    item_id: str
    title: str
    description: str
    category: str
