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
    def test_tc266_registry_contains_exact_production_scenario(self):
        registry = _get_registry()

        self.assertEqual(registry.ids(), ("getting_started_generation",))
        scenario = registry.get("getting_started_generation")
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.target.scope, CaptureScope.FULL_WINDOW)
        self.assertIsNone(scenario.target.semantic_id)
        self.assertEqual(scenario.profile.window_size, (960, 540))
        self.assertEqual(scenario.profile.fps, 10)
        self.assertEqual(scenario.profile.output_scale, 1.0)
        self.assertEqual(scenario.profile.default_wait_timeout_ms, 3000)
        self.assertEqual(scenario.output.filename, "getting_started_generation.gif")
        self.assertEqual(scenario.output.format, OutputFormat.GIF)

    def test_tc267_scenario_uses_only_locked_safe_semantic_actions(self):
        scenario = _get_registry().get("getting_started_generation")

        self.assertEqual(
            scenario.actions,
            (
                WaitVisibleAction("navigation.video_workspace"),
                HoldAction(500),
                ClickAction("navigation.video_workspace"),
                WaitVisibleAction("workspace.ai_generation"),
                WaitSettledAction(),
                HoldAction(1500),
            ),
        )
        self.assertTrue(
            all(
                isinstance(action, (ClickAction, WaitVisibleAction, HoldAction, WaitSettledAction))
                for action in scenario.actions
            )
        )

    def test_tc268_cli_list_preserves_existing_count_only_contract(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["list"])

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), "Listing 1 scenarios...")
        self.assertNotIn("getting_started_generation", output.getvalue())


if __name__ == "__main__":
    unittest.main()
