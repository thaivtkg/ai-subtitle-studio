import unittest

from core.tutorial.models import (
    AnchorHandle, AnchorResolution, AnchorStatus, CalloutSpec, SafetySpec,
    TargetPolicy, TourDefinition, TourStep, TourStepType,
)
from core.tutorial.environment import TourEnvironment
from core.tutorial.ports import (
    NavigationPort, AnchorRegistryPort, InteractionObserverPort,
    SpotlightPort, DialogObserverPort, ProgressStorePort,
)

from core.tutorial.tour_engine import TourEngine, TourState


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


class _Catalog:
    def __init__(self, guide):
        self.guide = guide

    def get_guide(self, guide_id):
        return self.guide if guide_id == self.guide.guide_id else None


class _Registry:
    def __init__(self):
        self.status = AnchorStatus.RESOLVED

    def resolve(self, anchor_id):
        if self.status is AnchorStatus.RESOLVED:
            return AnchorResolution(AnchorStatus.RESOLVED, AnchorHandle(anchor_id, "host", 1))
        return AnchorResolution(self.status)


class _Observer:
    def __init__(self):
        self.bound = False

    def bind(self, anchor, interaction, *, session_id, generation):
        self.bound = True

    def unbind(self):
        self.bound = False

    def is_bound(self):
        return self.bound


class _DialogObserver:
    def __init__(self):
        self.started = []
        self.stopped = 0

    def start(self, session_id):
        self.started.append(session_id)

    def stop(self):
        self.stopped += 1

    def active_modal_handle(self):
        return None


class _Spotlight:
    def __init__(self):
        self.history = []

    def show_recovery(self, message, *, retry_enabled, skip_enabled):
        self.history.append("RECOVERY")

    def show_info_without_target(self, callout, controls):
        self.history.append("INFO_NO_TARGET")

    def show_target(self, anchor, callout, controls):
        self.history.append("TARGET")
        return True

    def show_demo(self, demo, callout, controls):
        self.history.append("DEMO")
        return True

    def hide_step(self):
        self.history.append("HIDE_STEP")

    def detach_host(self):
        self.history.append("DETACH_HOST")


class TestTourEngineA4(unittest.TestCase):
    def setUp(self):
        callout = CalloutSpec("Title", "Body")
        guide = TourDefinition(
            1, "test_guide", 1, "Test", "test", 1,
            (
                TourStep("step1", TourStepType.INFO, callout, SafetySpec(True), anchor="btn1", target_policy=TargetPolicy.REQUIRED),
                TourStep("step2", TourStepType.ACTION, callout, SafetySpec(False), anchor="btn2", target_policy=TargetPolicy.SKIP),
                TourStep("step3", TourStepType.INFO, callout, SafetySpec(True), anchor="btn3", target_policy=TargetPolicy.FALLBACK_TO_INFO),
            ),
        )
        self.registry = _Registry()
        self.observer = _Observer()
        self.dialog = _DialogObserver()
        self.spotlight = _Spotlight()
        self.engine = TourEngine(
            _Catalog(guide), self.registry, None, self.observer, self.spotlight,
            self.dialog, None, TourEnvironment(lambda _: True),
        )

    def test_tc147_missing_anchor_policies(self):
        self.registry.status = AnchorStatus.NOT_FOUND
        self.assertTrue(self.engine.start("test_guide"))
        self.assertEqual(self.engine.state(), TourState.RECOVERING)
        self.assertIn("RECOVERY", self.spotlight.history)

        self.engine._current_step_index = 1
        self.engine._process_current_step()
        self.assertEqual(self.engine.state(), TourState.SHOWING_INFO)
        self.assertIn("INFO_NO_TARGET", self.spotlight.history)

    def test_tc155_info_demo_back_rebuilds_previous(self):
        self.registry.status = AnchorStatus.RESOLVED
        self.engine.start("test_guide")
        self.engine._current_step_index = 2
        self.engine._state = TourState.SHOWING_INFO
        generation = self.engine._generation
        self.engine.back()
        self.assertEqual(self.engine._current_step_index, 1)
        self.assertEqual(self.engine._generation, generation + 1)
        self.assertIn("HIDE_STEP", self.spotlight.history)

    def test_tc156_action_back_disabled(self):
        self.engine.start("test_guide")
        self.engine._current_step_index = 1
        self.engine._state = TourState.WAITING_ACTION
        self.engine.back()
        self.assertEqual(self.engine._current_step_index, 1)

    def test_tc157_cancel_triggers_full_cleanup(self):
        self.engine.start("test_guide")
        self.observer.bound = True
        cancelled = []
        self.engine.tour_cancelled.connect(lambda session, reason: cancelled.append((session, reason)))
        self.engine.cancel("TEST_REASON")
        self.assertFalse(self.observer.bound)
        self.assertEqual(self.engine.state(), TourState.CANCELLED)
        self.assertIn("HIDE_STEP", self.spotlight.history)
        self.assertIn("DETACH_HOST", self.spotlight.history)
        self.assertEqual(self.dialog.stopped, 1)
        self.assertEqual(cancelled[0][1], "TEST_REASON")


if __name__ == "__main__":
    unittest.main()
