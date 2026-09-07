import unittest

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import CaptureProfile, WaitHiddenAction, WaitVisibleAction
from ui.demo_capture.action_driver import UIActionDriver


class MockResolver:
    def __init__(self):
        self.behavior = []

    def resolve_widget(self, semantic_id: str):
        if not self.behavior:
            raise RuntimeError("Mock out of behavior")
        result = self.behavior.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class TestDemoCaptureWaitsC4(unittest.TestCase):
    def setUp(self):
        self.resolver = MockResolver()
        self.pump_calls = 0
        self.tick_calls = 0
        self.current_time = 0.0
        self.profile = CaptureProfile(default_wait_timeout_ms=3000)

        def mock_pump():
            self.pump_calls += 1

        def mock_tick():
            self.tick_calls += 1
            self.current_time += 0.5

        self.driver = UIActionDriver(
            resolver=self.resolver,
            event_pump=mock_pump,
            clock=lambda: self.current_time,
        )
        self.tick = mock_tick

    def _err(self, code):
        return CaptureRunError(error_code=code, message="")

    def test_tc198_wait_visible_semantics(self):
        action = WaitVisibleAction("target", timeout_ms=1500)
        self.resolver.behavior = [
            self._err(CaptureErrorCode.TARGET_NOT_FOUND),
            self._err(CaptureErrorCode.TARGET_NOT_VISIBLE),
            "MockWidget",
        ]
        self.driver.execute(action, self.profile, self.tick)
        self.assertEqual(self.pump_calls, 3)

        self.resolver.behavior = [self._err(CaptureErrorCode.TARGET_INVALID)]
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(action, self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_INVALID)

        self.current_time = 0.0
        self.resolver.behavior = [self._err(CaptureErrorCode.TARGET_NOT_FOUND)] * 10
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(action, self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.WAIT_TIMEOUT)

    def test_tc199_wait_hidden_semantics(self):
        action = WaitHiddenAction("target", timeout_ms=1500)
        self.resolver.behavior = [
            "MockWidget",
            self._err(CaptureErrorCode.TARGET_NOT_VISIBLE),
        ]
        self.driver.execute(action, self.profile, self.tick)
        self.assertEqual(self.pump_calls, 2)

        self.resolver.behavior = [self._err(CaptureErrorCode.TARGET_NOT_FOUND)]
        self.driver.execute(action, self.profile, self.tick)

        self.resolver.behavior = [self._err(CaptureErrorCode.TARGET_RESOLUTION_ERROR)]
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(action, self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_RESOLUTION_ERROR)


if __name__ == "__main__":
    unittest.main()
