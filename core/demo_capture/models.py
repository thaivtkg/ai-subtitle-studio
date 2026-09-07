from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Optional, Sequence, Tuple


class CaptureScope(str, Enum):
    TARGET_REGION = "TARGET_REGION"
    FULL_WINDOW = "FULL_WINDOW"


class OutputFormat(str, Enum):
    PNG = "PNG"
    GIF = "GIF"


class ExecutionMode(str, Enum):
    ISOLATED = "ISOLATED"
    REAL_APP = "REAL_APP"


@dataclass(frozen=True)
class CaptureTarget:
    semantic_id: Optional[str]
    scope: CaptureScope = CaptureScope.TARGET_REGION
    padding: int = 16

    def __post_init__(self) -> None:
        if self.padding < 0:
            raise ValueError("padding must be >= 0")
        if self.scope is CaptureScope.TARGET_REGION and not self.semantic_id:
            raise ValueError("TARGET_REGION requires semantic_id")
        if self.scope is CaptureScope.FULL_WINDOW and self.semantic_id is not None:
            raise ValueError("FULL_WINDOW requires semantic_id=None")


@dataclass(frozen=True)
class CaptureProfile:
    window_size: Tuple[int, int] = (800, 600)
    fps: int = 10
    output_scale: float = 1.0
    default_wait_timeout_ms: int = 3000

    def __post_init__(self) -> None:
        width, height = self.window_size
        if width <= 0 or height <= 0:
            raise ValueError("window dimensions must be > 0")
        if not 1 <= self.fps <= 30:
            raise ValueError("fps must be in range 1..30")
        if self.output_scale <= 0:
            raise ValueError("output_scale must be > 0")
        if self.default_wait_timeout_ms <= 0:
            raise ValueError("default_wait_timeout_ms must be > 0")


@dataclass(frozen=True)
class OutputSpec:
    filename: str
    format: OutputFormat

    def __post_init__(self) -> None:
        if self.filename != PurePosixPath(self.filename).name or self.filename != PureWindowsPath(self.filename).name:
            raise ValueError("filename must be basename only")

        extension = PurePosixPath(self.filename).suffix.lower()
        if self.format == OutputFormat.GIF and extension != ".gif":
            raise ValueError("format mismatch")
        if self.format == OutputFormat.PNG and extension != ".png":
            raise ValueError("format mismatch")


@dataclass(frozen=True)
class CaptureAction:
    pass


@dataclass(frozen=True)
class ClickAction(CaptureAction):
    target: str

    def __post_init__(self) -> None:
        if not self.target:
            raise ValueError("target cannot be empty")


@dataclass(frozen=True)
class SetTextAction(CaptureAction):
    target: str
    text: str


@dataclass(frozen=True)
class SelectAction(CaptureAction):
    target: str
    option: str


@dataclass(frozen=True)
class NavigateAction(CaptureAction):
    destination: str


@dataclass(frozen=True)
class WaitVisibleAction(CaptureAction):
    target: str
    timeout_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be > 0")


@dataclass(frozen=True)
class WaitHiddenAction(CaptureAction):
    target: str
    timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class WaitSettledAction(CaptureAction):
    timeout_ms: Optional[int] = None


@dataclass(frozen=True)
class HoldAction(CaptureAction):
    duration_ms: int

    def __post_init__(self) -> None:
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be > 0")


@dataclass(frozen=True)
class CaptureScenario:
    id: str
    target: CaptureTarget
    profile: CaptureProfile
    actions: Sequence[CaptureAction]
    output: OutputSpec
