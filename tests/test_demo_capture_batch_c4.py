import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.demo_capture.batch import BatchProcessor
from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import ExecutionMode, OutputFormat, OutputSpec


class TestDemoCaptureBatchC4(unittest.TestCase):
    def setUp(self):
        self.scenarios = [
            MagicMock(id="A", output=OutputSpec("A.gif", OutputFormat.GIF)),
            MagicMock(id="B", output=OutputSpec("B.gif", OutputFormat.GIF)),
            MagicMock(id="C", output=OutputSpec("C.gif", OutputFormat.GIF)),
        ]
        self.registry = MagicMock()
        self.registry.all.return_value = self.scenarios
        self.writer = MagicMock()
        self.call_count = 0

        def runner(scenario, mode, staging_dir):
            self.call_count += 1
            if scenario.id == "B" and hasattr(self, "fail_B"):
                raise RuntimeError("B Failed")
            return Path("staged") / scenario.output.filename

        self.processor = BatchProcessor(self.registry, Path("staging"), self.writer, runner)

    def test_tc242_fresh_environment(self):
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.assertEqual(self.call_count, 3)

    def test_tc243_all_or_nothing(self):
        self.fail_B = True
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.writer.commit.assert_not_called()

    def test_tc244_continue_after_failure(self):
        self.fail_B = True
        results = self.processor.run_all(ExecutionMode.ISOLATED)
        self.assertEqual(self.call_count, 3)
        errors = [error for _, _, error in results if error]
        self.assertEqual(len(errors), 1)
        self.assertEqual(str(errors[0]), "B Failed")

    def test_tc245_real_app_forbidden(self):
        with self.assertRaises(CaptureRunError) as error:
            self.processor.run_all(ExecutionMode.REAL_APP)
        self.assertEqual(error.exception.error_code, CaptureErrorCode.INVALID_SCENARIO)

    def test_tc246_commit_phase_starts_last(self):
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.assertEqual(self.writer.commit.call_count, 3)


if __name__ == "__main__":
    unittest.main()
