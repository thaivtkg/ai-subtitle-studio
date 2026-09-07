from typing import Callable

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError


class FrameClock:
    def __init__(self, fps: int, clock_fn: Callable[[], float]):
        self._fps = fps
        self._clock = clock_fn
        self._start_time = None
        self._last_time = None
        self._last_yielded = 0

    def start(self) -> None:
        now = self._clock()
        self._start_time = now
        self._last_time = now
        self._last_yielded = 0

    def due_count(self) -> int:
        if self._start_time is None:
            return 0

        now = self._clock()
        if self._last_time is not None and now < self._last_time:
            raise CaptureRunError(CaptureErrorCode.CAPTURE_FAILED, "Monotonic clock moved backwards")
        self._last_time = now

        elapsed = now - self._start_time
        total_due = int(round(elapsed * self._fps, 6))
        due = total_due - self._last_yielded
        self._last_yielded = total_due
        return due
