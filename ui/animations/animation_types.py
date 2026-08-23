from dataclasses import dataclass
from enum import Enum

class SubtitleAppearMode(Enum):
    INSTANT = "instant"
    FADE = "fade"
    RISE = "rise"
    REVEAL = "reveal"

class SubtitleDisappearMode(Enum):
    INSTANT = "instant"
    FADE = "fade"
    DROP = "drop"

class SubtitleTextEffect(Enum):
    NORMAL = "normal"
    REVEAL = "reveal"
    HIGHLIGHT = "highlight"

class SubtitleAnimationState(Enum):
    HIDDEN = "hidden"
    ENTERING = "entering"
    VISIBLE = "visible"
    EXITING = "exiting"

@dataclass(frozen=True)
class SubtitleRenderInput:
    """Hợp đồng dữ liệu hiển thị bất biến (Immutable Presentation Input)"""
    segment_id: int
    start_ms: int
    end_ms: int
    text: str