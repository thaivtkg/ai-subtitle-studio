import io
import unittest
from contextlib import redirect_stdout

from core.demo_capture.models import (
    CaptureScope,
    ClickAction,
    HoldAction,
    OutputFormat,
    WaitSettledAction,
    WaitVisibleAction,
)
from tools.demo_capture.cli import _get_registry, main


class TestC5ProductionCaptureScenario(unittest.TestCase):
    def test_production_registry_exposes_safe_generation_scenario(self):
        registry = _get_registry()

        self.assertEqual(registry.ids(), ("getting_started_generation",))
        scenario = registry.get("getting_started_generation")
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.target.scope, CaptureScope.FULL_WINDOW)
        self.assertIsNone(scenario.target.semantic_id)
        self.assertEqual(scenario.profile.window_size, (960, 540))
        self.assertEqual(scenario.profile.fps, 10)
        self.assertEqual(scenario.output.filename, "getting_started_generation.gif")
        self.assertEqual(scenario.output.format, OutputFormat.GIF)
        self.assertEqual(
            scenario.actions,
            (
                ClickAction("navigation.video_workspace"),
                WaitVisibleAction("workspace.ai_generation"),
                HoldAction(1000),
                WaitSettledAction(),
            ),
        )
        self.assertTrue(
            all(
                isinstance(action, (ClickAction, WaitVisibleAction, HoldAction, WaitSettledAction))
                for action in scenario.actions
            )
        )

    def test_cli_list_reports_production_scenario(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["list"])

        self.assertEqual(result, 0)
        self.assertIn("Listing 1 scenarios...", output.getvalue())


if __name__ == "__main__":
    unittest.main()
