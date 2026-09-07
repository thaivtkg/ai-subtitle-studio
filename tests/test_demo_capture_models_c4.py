import unittest
from dataclasses import FrozenInstanceError

from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureScope,
    CaptureTarget,
    ClickAction,
    HoldAction,
    OutputFormat,
    OutputSpec,
    WaitVisibleAction,
)


class TestDemoCaptureModelsC4(unittest.TestCase):
    def test_tc187_target_region_requires_semantic_id_and_defaults_padding(self):
        target = CaptureTarget(semantic_id="workspace.generate_panel")
        self.assertEqual(target.scope, CaptureScope.TARGET_REGION)
        self.assertEqual(target.padding, 16)
        with self.assertRaises(ValueError):
            CaptureTarget(semantic_id=None)

    def test_tc188_full_window_requires_no_semantic_id(self):
        target = CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None, padding=16)
        self.assertEqual(target.scope, CaptureScope.FULL_WINDOW)
        with self.assertRaises(ValueError):
            CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id="workspace")

    def test_tc189_profile_defaults_and_bounds(self):
        profile = CaptureProfile()
        self.assertEqual(profile.window_size, (800, 600))
        self.assertEqual(profile.fps, 10)
        self.assertEqual(profile.output_scale, 1.0)
        self.assertEqual(profile.default_wait_timeout_ms, 3000)
        for kwargs in (
            {"window_size": (0, 600)}, {"fps": 0}, {"fps": 31},
            {"output_scale": 0}, {"default_wait_timeout_ms": 0},
        ):
            with self.assertRaises(ValueError):
                CaptureProfile(**kwargs)

    def test_tc190_output_spec_confines_filename(self):
        self.assertEqual(
            OutputSpec("demo.gif", OutputFormat.GIF).filename,
            "demo.gif",
        )
        for name in ("../demo.gif", "folder/demo.gif", "C:\\demo.gif", "/tmp/demo.gif"):
            with self.assertRaises(ValueError):
                OutputSpec(name, OutputFormat.GIF)
        with self.assertRaises(ValueError):
            OutputSpec("demo.png", OutputFormat.GIF)

    def test_tc191_actions_are_typed_immutable_and_validate(self):
        action = ClickAction("workspace.generate_button")
        with self.assertRaises(FrozenInstanceError):
            action.target = "other"
        with self.assertRaises(ValueError):
            ClickAction("")
        with self.assertRaises(ValueError):
            HoldAction(0)
        with self.assertRaises(ValueError):
            WaitVisibleAction("x", timeout_ms=0)

    def test_tc192_scenario_is_immutable_and_preserves_action_order(self):
        actions = (ClickAction("a"), HoldAction(100))
        scenario = CaptureScenario(
            id="sample",
            target=CaptureTarget("a"),
            profile=CaptureProfile(),
            actions=actions,
            output=OutputSpec("sample.gif", OutputFormat.GIF),
        )
        self.assertEqual(scenario.actions, actions)
        with self.assertRaises(FrozenInstanceError):
            scenario.id = "changed"


if __name__ == "__main__":
    unittest.main()
