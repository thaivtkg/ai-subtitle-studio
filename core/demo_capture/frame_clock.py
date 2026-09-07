from typing import Callable

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError


class FrameClock:
    def __init__(self, fps: int, clock_fn: Callable[[], float]):
        self._fps = fps
        self._clock = clock_fn
        self._interval = 1.0 / fps
        self._start_time = None
        self._last_yielded = 0

    def start(self) -> None:
        self._start_time = self._clock()
        self._last_yielded = 0

    def due_count(self) -> int:
        if self._start_time is None:
            return 0

        elapsed = self._clock() - self._start_time
        if elapsed < 0:
            raise CaptureRunError(CaptureErrorCode.CAPTURE_FAILED, "Monotonic clock moved backwards")

        total_due = int(elapsed // self._interval)
        due = total_due - self._last_yielded
        self._last_yielded = total_due
        return due
