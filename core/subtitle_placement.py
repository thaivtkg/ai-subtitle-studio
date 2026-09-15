from dataclasses import dataclass, replace
from typing import Callable


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class SubtitlePlacementState:
    mode: str = "bottom"
    x: float = 0.5
    y: float = 0.85

    def __post_init__(self):
        self.mode = str(self.mode).lower()
        if self.mode not in {"top", "center", "bottom", "custom"}:
            self.mode = "bottom"
        self.x = _clamp(self.x)
        self.y = _clamp(self.y)


def normalized_to_pixel_anchor(width: int, height: int, x: float, y: float) -> tuple[int, int]:
    return round(_clamp(x) * width), round(_clamp(y) * height)


def complete_drag(placement: SubtitlePlacementState, x: float, y: float) -> SubtitlePlacementState:
    return replace(placement, mode="custom", x=x, y=y)


def set_mode(placement: SubtitlePlacementState, mode: str) -> SubtitlePlacementState:
    return replace(placement, mode=mode)


class PlacementEditSession:
    def __init__(self, on_commit: Callable[[SubtitlePlacementState], None], placement=None):
        self._on_commit = on_commit
        self._placement = placement or SubtitlePlacementState()
        self._pending = self._placement
        self._moved = False
        self._released = False

    def move(self, x: float, y: float) -> SubtitlePlacementState:
        if self._released:
            return self._pending
        self._pending = complete_drag(self._pending, x, y)
        self._moved = self._moved or self._pending != self._placement
        return self._pending

    def release(self) -> SubtitlePlacementState:
        if not self._released:
            self._released = True
            if self._moved:
                self._on_commit(self._pending)
        return self._pending
