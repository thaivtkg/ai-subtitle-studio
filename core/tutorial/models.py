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


class Precondition(str, Enum):
    PROJECT_OPEN = "PROJECT_OPEN"
    MEDIA_LOADED = "MEDIA_LOADED"
    NO_BACKGROUND_JOB = "NO_BACKGROUND_JOB"


class AnchorStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"
    NOT_VISIBLE = "NOT_VISIBLE"


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
    safety: SafetySpec
    surface: Optional[SurfaceSpec] = None
    anchor: Optional[str] = None
    target_policy: TargetPolicy = TargetPolicy.FALLBACK_TO_INFO
    interaction: Optional[InteractionSpec] = None
    demo: Optional[DemoSpec] = None
    preconditions: Tuple[Precondition, ...] = field(default_factory=tuple)


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
    preconditions: Tuple[Precondition, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AnchorHandle:
    """Opaque identity for a safely resolved UI anchor."""
    anchor_id: str
    host_id: str
    resolution_generation: int


@dataclass(frozen=True)
class AnchorResolution:
    status: AnchorStatus
    handle: Optional[AnchorHandle] = None
    reason: Optional[str] = None
