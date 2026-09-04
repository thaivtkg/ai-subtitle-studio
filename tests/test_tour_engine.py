import unittest

from core.tutorial.models import AnchorHandle, AnchorResolution, AnchorStatus
from core.tutorial.environment import TourEnvironment
from core.tutorial.ports import (
    NavigationPort, AnchorRegistryPort, InteractionObserverPort,
    SpotlightPort, DialogObserverPort, ProgressStorePort,
)


class TestTourEngineCoreContracts(unittest.TestCase):
    def test_anchor_resolution_default(self):
        resolution = AnchorResolution(AnchorStatus.NOT_FOUND)
        self.assertEqual(resolution.status, AnchorStatus.NOT_FOUND)
        self.assertIsNone(resolution.handle)
        self.assertIsNone(resolution.reason)

    def test_anchor_handle_is_opaque(self):
        handle = AnchorHandle("btn", "main", 1)
        self.assertFalse(hasattr(handle, "widget"))
        self.assertFalse(hasattr(handle, "qobject"))

    def test_tour_environment_delegates_to_checker(self):
        seen = []
        env = TourEnvironment(lambda key: seen.append(key) or key == "PROJECT_OPEN")
        self.assertTrue(env.check("PROJECT_OPEN"))
        self.assertFalse(env.check("NO_BACKGROUND_JOB"))
        self.assertEqual(seen, ["PROJECT_OPEN", "NO_BACKGROUND_JOB"])

    def test_protocols_interface_present(self):
        for protocol, method in (
            (NavigationPort, "navigate"),
            (AnchorRegistryPort, "resolve"),
            (InteractionObserverPort, "bind"),
            (SpotlightPort, "show_target"),
            (DialogObserverPort, "start"),
            (ProgressStorePort, "is_completed"),
        ):
            self.assertTrue(hasattr(protocol, method))


if __name__ == "__main__":
    unittest.main()
