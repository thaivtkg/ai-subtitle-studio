from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class TourStepType(str, Enum):
    INFO = "INFO"
    ACTION = "ACTION"
    DEMO = "DEMO"


class InteractionKind(str, Enum):
    CLICK = "CLICK"
    FOCUS = "FOCUS"
    TEXT_COMMITTED = "TEXT_COMMITTED"
    SELECTION_CHANGED = "SELECTION_CHANGED"
    DIALOG_ACCEPTED = "DIALOG_ACCEPTED"


class TargetPolicy(str, Enum):
    REQUIRED = "REQUIRED"
    FALLBACK_TO_INFO = "FALLBACK_TO_INFO"
    SKIP = "SKIP"


class CalloutPlacement(str, Enum):
    AUTO = "auto"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


class TourState(str, Enum):
    IDLE = "IDLE"
    PREPARING_SURFACE = "PREPARING_SURFACE"
    RESOLVING_TARGET = "RESOLVING_TARGET"
    SHOWING_INFO = "SHOWING_INFO"
    WAITING_ACTION = "WAITING_ACTION"
    SHOWING_DEMO = "SHOWING_DEMO"
    ADVANCING_STEP = "ADVANCING_STEP"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class SurfaceSpec:
    route: str
    subroute: Optional[str] = None


@dataclass(frozen=True)
class CalloutSpec:
    title: str
    body: str
    placement: CalloutPlacement = CalloutPlacement.AUTO


@dataclass(frozen=True)
class InteractionSpec:
    kind: InteractionKind


@dataclass(frozen=True)
class DemoSpec:
    asset: str
    media_type: str
    fit: str = "contain"


@dataclass(frozen=True)
class SafetySpec:
    allow_back: bool
    allow_skip_step: bool = True
    allow_skip_tour: bool = True


@dataclass(frozen=True)
class TourStep:
    step_id: str
    step_type: TourStepType
    callout: CalloutSpec
    surface: Optional[SurfaceSpec] = None
    anchor: Optional[str] = None
    target_policy: TargetPolicy = TargetPolicy.FALLBACK_TO_INFO
    interaction: Optional[InteractionSpec] = None
    demo: Optional[DemoSpec] = None
    safety: SafetySpec = field(default_factory=lambda: SafetySpec(allow_back=True))


@dataclass(frozen=True)
class TourDefinition:
    schema_version: int
    guide_id: str
    content_version: int
    title: str
    category: str
    estimated_minutes: int
    steps: Tuple[TourStep, ...]
    description: str = ""
