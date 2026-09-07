from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import CaptureAction, CaptureProfile, WaitHiddenAction, WaitVisibleAction
from core.demo_capture.ports import Clock, EventPump, TargetResolverPort, TickCallback


class UIActionDriver:
    def __init__(self, resolver: TargetResolverPort, event_pump: EventPump, clock: Clock):
        self._resolver = resolver
        self._event_pump = event_pump
        self._clock = clock

    def execute(self, action: CaptureAction, profile: CaptureProfile, tick: TickCallback) -> None:
        if isinstance(action, WaitVisibleAction):
            self._wait_visible(action, profile, tick)
        elif isinstance(action, WaitHiddenAction):
            self._wait_hidden(action, profile, tick)
        else:
            raise NotImplementedError(f"Action type {type(action).__name__} not yet implemented")

    def _wait_visible(self, action: WaitVisibleAction, profile: CaptureProfile, tick: TickCallback) -> None:
        timeout_ms = action.timeout_ms if action.timeout_ms is not None else profile.default_wait_timeout_ms
        start_time = self._clock()

        while True:
            self._event_pump()
            try:
                self._resolver.resolve_widget(action.target)
                return
            except CaptureRunError as error:
                if error.error_code not in (CaptureErrorCode.TARGET_NOT_FOUND, CaptureErrorCode.TARGET_NOT_VISIBLE):
                    raise

            tick()
            if (self._clock() - start_time) * 1000 >= timeout_ms:
                raise CaptureRunError(
                    error_code=CaptureErrorCode.WAIT_TIMEOUT,
                    message=f"Timeout waiting for '{action.target}' to become visible",
                    target=action.target,
                )

    def _wait_hidden(self, action: WaitHiddenAction, profile: CaptureProfile, tick: TickCallback) -> None:
        timeout_ms = action.timeout_ms if action.timeout_ms is not None else profile.default_wait_timeout_ms
        start_time = self._clock()

        while True:
            self._event_pump()
            try:
                self._resolver.resolve_widget(action.target)
            except CaptureRunError as error:
                if error.error_code in (CaptureErrorCode.TARGET_NOT_FOUND, CaptureErrorCode.TARGET_NOT_VISIBLE):
                    return
                raise

            tick()
            if (self._clock() - start_time) * 1000 >= timeout_ms:
                raise CaptureRunError(
                    error_code=CaptureErrorCode.WAIT_TIMEOUT,
                    message=f"Timeout waiting for '{action.target}' to hide",
                    target=action.target,
                )
