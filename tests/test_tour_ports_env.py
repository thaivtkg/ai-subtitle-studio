import unittest
from dataclasses import FrozenInstanceError

from core.tutorial.models import AnchorHandle, AnchorResolution, AnchorStatus, Precondition

try:
    from core.tutorial.environment import TourEnvironment
    from core.tutorial.ports import NavigationAdapterPort, SpotlightLayerPort
except (ImportError, ModuleNotFoundError):
    TourEnvironment = None
    NavigationAdapterPort = None
    SpotlightLayerPort = None


class TestTourPortsAndEnvironment(unittest.TestCase):
    def test_anchor_models_are_frozen(self):
        handle = AnchorHandle("btn", "main", 1)
        with self.assertRaises(FrozenInstanceError):
            handle.anchor_id = "hacked"
        resolution = AnchorResolution(AnchorStatus.RESOLVED, handle)
        with self.assertRaises(FrozenInstanceError):
            resolution.status = AnchorStatus.NOT_FOUND

    def test_anchor_status_enum_is_complete(self):
        self.assertEqual({status.value for status in AnchorStatus}, {
            "RESOLVED", "NOT_FOUND", "INVALID", "NOT_VISIBLE"
        })

    @unittest.skipIf(TourEnvironment is None, "Qt ports unavailable")
    def test_environment_is_read_only_interface(self):
        with self.assertRaises(NotImplementedError):
            TourEnvironment().check(Precondition.PROJECT_OPEN)

    @unittest.skipIf(NavigationAdapterPort is None, "Qt ports unavailable")
    def test_ports_raise_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            NavigationAdapterPort().cancel_pending()
        with self.assertRaises(NotImplementedError):
            SpotlightLayerPort().hide_step()


if __name__ == "__main__":
    unittest.main()
