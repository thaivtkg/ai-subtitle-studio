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
        self.staging_dir = Path("test_staging_batch")
        self.staging_dir.mkdir(exist_ok=True)
        self.call_count = 0

        def runner(scenario, mode, staging_dir):
            self.call_count += 1
            staged_file = staging_dir / scenario.output.filename
            staged_file.write_text("dummy")
            if scenario.id == "B" and hasattr(self, "fail_B"):
                raise RuntimeError("B Failed")
            return staged_file

        self.processor = BatchProcessor(self.registry, self.staging_dir, self.writer, runner)

    def tearDown(self):
        for path in self.staging_dir.glob("*"):
            path.unlink()
        self.staging_dir.rmdir()

    def test_tc242_fresh_environment(self):
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.assertEqual(self.call_count, 3)

    def test_tc243_all_or_nothing(self):
        self.fail_B = True
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.writer.commit.assert_not_called()
        self.assertFalse(any(self.staging_dir.iterdir()))

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
        events = []

        def runner(scenario, mode, staging_dir):
            events.append(f"stage_{scenario.id}")
            return staging_dir / scenario.output.filename

        self.writer.commit.side_effect = lambda path, spec: events.append(
            f"commit_{spec.filename[0]}"
        )
        self.processor.runner_fn = runner
        self.processor.run_all(ExecutionMode.ISOLATED)
        self.assertEqual(
            events,
            ["stage_A", "stage_B", "stage_C", "commit_A", "commit_B", "commit_C"],
        )


if __name__ == "__main__":
    unittest.main()
