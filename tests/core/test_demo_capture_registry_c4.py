import unittest

from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureTarget,
    HoldAction,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.registry import DemoScenarioRegistry


class TestDemoScenarioRegistryC4(unittest.TestCase):
    def _scenario(self, scenario_id, filename):
        return CaptureScenario(
            id=scenario_id,
            target=CaptureTarget("fixture.anchor"),
            profile=CaptureProfile(),
            actions=(HoldAction(50),),
            output=OutputSpec(filename, OutputFormat.GIF),
        )

    def test_tc193_duplicate_scenario_id_rejected(self):
        a = self._scenario("dup", "a.gif")
        b = self._scenario("dup", "b.gif")
        with self.assertRaises(ValueError):
            DemoScenarioRegistry((a, b))

    def test_tc194_duplicate_output_rejected(self):
        a = self._scenario("a", "same.gif")
        b = self._scenario("b", "same.gif")
        with self.assertRaises(ValueError):
            DemoScenarioRegistry((a, b))

    def test_tc195_registry_is_structural_only(self):
        registry = DemoScenarioRegistry((self._scenario("a", "a.gif"),))
        self.assertEqual(registry.ids(), ("a",))
        self.assertEqual(registry.get("a").output.filename, "a.gif")
        self.assertIsNone(registry.get("missing"))

        bad_scenario = CaptureScenario(
            id="bad",
            target=CaptureTarget("fixture.anchor"),
            profile=CaptureProfile(),
            actions=("not-an-action",),
            output=OutputSpec("bad.gif", OutputFormat.GIF),
        )
        with self.assertRaises(ValueError):
            DemoScenarioRegistry((bad_scenario,))


if __name__ == "__main__":
    unittest.main()
