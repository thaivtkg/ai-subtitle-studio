import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureTarget,
    ExecutionMode,
    HoldAction,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.runner import capture_to_staging


class TestDemoCaptureRunnerC4(unittest.TestCase):
    def setUp(self):
        self.scenario = CaptureScenario(
            id="test",
            target=CaptureTarget("t"),
            profile=CaptureProfile(),
            actions=(HoldAction(10), HoldAction(10)),
            output=OutputSpec("t.gif", OutputFormat.GIF),
        )
        self.staging = Path("staging")
        self.mock_env = MagicMock()
        self.mock_env.__enter__.return_value = (MagicMock(), MagicMock(), MagicMock())
        self.mock_env_factory = MagicMock(return_value=self.mock_env)
        self.clock = MagicMock()
        self.capture = MagicMock()
        self.capture.capture.return_value = "FRAME"
        self.normalizer = MagicMock()
        self.encoder = MagicMock()
        self.validator = MagicMock()

    def _run(self):
        return capture_to_staging(
            self.scenario,
            ExecutionMode.ISOLATED,
            self.staging,
            self.mock_env_factory,
            self.clock,
            self.capture,
            self.normalizer,
            self.encoder,
            self.validator,
        )

    def test_tc231_initial_final_frames(self):
        self._run()
        self.assertEqual(self.capture.capture.call_count, 2)
        self.normalizer.normalize.assert_called_with(["FRAME", "FRAME"], 1.0)

    def test_tc232_action_order_and_cadence(self):
        self.clock.due_count.return_value = 2
        driver = self.mock_env.__enter__.return_value[1]
        driver.execute.side_effect = lambda action, profile, tick: tick()
        self._run()
        self.assertEqual(self.capture.capture.call_count, 6)

    def test_tc233_structured_failure(self):
        driver = self.mock_env.__enter__.return_value[1]
        driver.execute.side_effect = [None, RuntimeError("Crash")]
        with self.assertRaises(CaptureRunError) as error:
            self._run()
        self.assertEqual(error.exception.error_code, CaptureErrorCode.ACTION_FAILED)
        self.assertEqual(error.exception.action_index, 1)

    def test_tc234_staging_failure_never_commits(self):
        self.validator.validate_file.side_effect = CaptureRunError(
            CaptureErrorCode.OUTPUT_VALIDATION_FAILED, ""
        )
        with self.assertRaises(CaptureRunError) as error:
            self._run()
        self.assertEqual(error.exception.error_code, CaptureErrorCode.OUTPUT_VALIDATION_FAILED)

    def test_tc235_cleanup_failure_fails_overall(self):
        self.mock_env.__exit__.side_effect = RuntimeError("Cleanup crashed")
        with self.assertRaises(CaptureRunError) as error:
            self._run()
        self.assertEqual(error.exception.error_code, CaptureErrorCode.CLEANUP_FAILED)


if __name__ == "__main__":
    unittest.main()
