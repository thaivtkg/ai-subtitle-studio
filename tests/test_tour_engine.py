import sys
import unittest

from core.tutorial.environment import TourEnvironment
from core.tutorial.models import (
    AnchorHandle, AnchorResolution, AnchorStatus, CalloutSpec, DemoSpec, InteractionSpec,
    SafetySpec, SurfaceSpec, TargetPolicy, TourDefinition, TourStep, TourStepType,
    TourState as ModelTourState,
)
from core.tutorial.ports import (
    AnchorRegistryPort, DialogObserverPort, InteractionObserverPort,
    NavigationPort, ProgressStorePort, SpotlightPort,
)
from core.tutorial.tour_engine import TourEngine, TourState

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

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
            (NavigationPort, "navigate"), (AnchorRegistryPort, "resolve"),
            (InteractionObserverPort, "bind"), (SpotlightPort, "show_target"),
            (DialogObserverPort, "start"), (ProgressStorePort, "is_completed"),
        ):
            self.assertTrue(hasattr(protocol, method))


class FakeCatalog:
    def __init__(self, guides): self.guides = guides
    def get_guide(self, guide_id): return self.guides.get(guide_id)


class FakeAnchorRegistry:
    def __init__(self): self.status = AnchorStatus.RESOLVED
    def resolve(self, anchor_id):
        if self.status is AnchorStatus.RESOLVED:
            return AnchorResolution(self.status, AnchorHandle(anchor_id, "host", 1))
        return AnchorResolution(self.status)


class FakeNavigation:
    def __init__(self): self.requests = []; self.cancel_pending_calls = 0
    def navigate(self, surface, *, session_id, generation, request_id):
        self.requests.append((session_id, generation, request_id))
    def current_surface(self): return None
    def cancel_pending(self): self.cancel_pending_calls += 1


class FakeObserver:
    def __init__(self): self.bound = False; self.unbind_calls = 0; self.binding = None
    def bind(self, anchor, interaction, *, session_id, generation):
        self.bound = True; self.binding = (session_id, generation)
    def unbind(self): self.bound = False; self.unbind_calls += 1
    def is_bound(self): return self.bound


class FakeSpotlight:
    def __init__(self): self.history = []
    def attach_host(self, host): return True
    def detach_host(self): self.history.append("DETACH_HOST")
    def hide_step(self): self.history.append("HIDE_STEP")
    def show_recovery(self, message, *, retry_enabled, skip_enabled): self.history.append("RECOVERY")
    def show_info_without_target(self, callout, controls): self.history.append("INFO_NO_TARGET")
    def show_target(self, anchor, callout, controls): self.history.append("TARGET"); return True
    def show_demo(self, demo, callout, controls): self.history.append("DEMO"); return True


class FakeDialogObserver:
    def __init__(self): self.started = []; self.stop_calls = 0
    def start(self, session_id): self.started.append(session_id)
    def stop(self): self.stop_calls += 1
    def active_modal_handle(self): return None


class FakeProgressStore:
    def __init__(self): self.completed = []
    def is_completed(self, guide_id, content_version): return False
    def mark_completed(self, guide_id, content_version): self.completed.append((guide_id, content_version))
    def mark_dismissed(self, guide_id, content_version): pass


class TestTourEngineA4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    def setUp(self):
        self.spotlight = FakeSpotlight(); self.registry = FakeAnchorRegistry()
        self.observer = FakeObserver(); self.dialog = FakeDialogObserver()
        self.progress = FakeProgressStore(); self.navigation = FakeNavigation()
        guide = TourDefinition(
            schema_version=1, guide_id="test_guide", content_version=1,
            title="Test", category="test", estimated_minutes=1,
            steps=(
                TourStep("required", TourStepType.ACTION, CalloutSpec("T1", "B1"), SafetySpec(True),
                         surface=SurfaceSpec("dash"), anchor="b1", target_policy=TargetPolicy.REQUIRED,
                         interaction=InteractionSpec("CLICK")),
                TourStep("skip", TourStepType.INFO, CalloutSpec("T2", "B2"), SafetySpec(True),
                         surface=SurfaceSpec("other"), anchor="b2", target_policy=TargetPolicy.SKIP),
                TourStep("fallback", TourStepType.ACTION, CalloutSpec("T3", "B3"), SafetySpec(False),
                         anchor="b3", target_policy=TargetPolicy.FALLBACK_TO_INFO,
                         interaction=InteractionSpec("CLICK")),
                TourStep("demo", TourStepType.DEMO, CalloutSpec("T4", "B4"), SafetySpec(True),
                         anchor="b4", target_policy=TargetPolicy.FALLBACK_TO_INFO),
            ),
        )
        self.catalog = FakeCatalog({"test_guide": guide})
        self.engine = self._new_engine(self.catalog, TourEnvironment(lambda _: True))

    def _new_engine(self, catalog, environment):
        return TourEngine(catalog=catalog, anchor_registry=self.registry, navigation=self.navigation,
                          interaction_observer=self.observer, spotlight=self.spotlight,
                          dialog_observer=self.dialog, progress_store=self.progress,
                          environment=environment, target_settle_timeout_ms=0)

    def _ready(self):
        self.engine.on_surface_ready(*self.navigation.requests[-1])

    def _settle(self):
        QCoreApplication.processEvents()

    def test_tc147_missing_anchor_policy(self):
        self.registry.status = AnchorStatus.NOT_FOUND
        self.assertTrue(self.engine.start("test_guide"))
        self.assertEqual(self.engine.state(), TourState.PREPARING_SURFACE)
        self._ready()
        self._settle()
        self.assertEqual(self.engine.state(), TourState.RECOVERING)
        self.engine.skip_step()
        self._ready()
        self._settle()
        self._settle()
        self.assertEqual(self.engine.state(), TourState.SHOWING_INFO)
        self.assertFalse(self.observer.is_bound())
        self.assertIn("INFO_NO_TARGET", self.spotlight.history)

    def test_tour_state_identity(self):
        from core.tutorial.tour_engine import TourState as EngineTourState
        self.assertIs(ModelTourState.CANCELLED, EngineTourState.CANCELLED)

    def test_action_and_navigation_cannot_be_bypassed_by_next(self):
        self.assertTrue(self.engine.start("test_guide"))
        self.assertEqual(self.engine.state(), ModelTourState.PREPARING_SURFACE)
        self.engine.next()
        self.assertEqual(self.engine.state(), ModelTourState.PREPARING_SURFACE)

        self._ready()
        self.assertEqual(self.engine.state(), ModelTourState.WAITING_ACTION)
        self.engine.next()
        self.assertEqual(self.engine.state(), ModelTourState.WAITING_ACTION)

    def test_anchorless_demo_displays_demo(self):
        self.catalog.guides["demo_guide"] = TourDefinition(
            schema_version=1, guide_id="demo_guide", content_version=1,
            title="Demo", category="test", estimated_minutes=1,
            steps=(TourStep("demo", TourStepType.DEMO, CalloutSpec("T", "B"),
                            SafetySpec(True), demo=DemoSpec("asset", "IMAGE")),),
        )
        self.assertTrue(self.engine.start("demo_guide"))
        self.assertEqual(self.engine.state(), ModelTourState.SHOWING_DEMO)
        self.assertIn("DEMO", self.spotlight.history)

    def test_anchorless_action_enters_recovery(self):
        self.catalog.guides["bad_guide"] = TourDefinition(
            schema_version=1, guide_id="bad_guide", content_version=1,
            title="Bad", category="test", estimated_minutes=1,
            steps=(TourStep("action", TourStepType.ACTION, CalloutSpec("T", "B"),
                            SafetySpec(True), anchor=None),),
        )
        self.assertTrue(self.engine.start("bad_guide"))
        self.assertEqual(self.engine.state(), ModelTourState.RECOVERING)

    def test_tc155_info_demo_back(self):
        self.assertTrue(self.engine.start("test_guide")); self._ready()
        self.engine.skip_step(); self._ready()
        self.engine.next(); self.engine.skip_step()
        self.assertEqual(self.engine.current_step().step_id, "demo")
        self.engine.back()
        self.assertEqual(self.engine.current_step().step_id, "fallback")
        self.assertIn("HIDE_STEP", self.spotlight.history)

    def test_tc156_action_back_disabled(self):
        self.assertTrue(self.engine.start("test_guide")); self._ready()
        self.engine.skip_step(); self._ready(); self.engine.next()
        self.assertEqual(self.engine.current_step().step_id, "fallback")
        self.assertEqual(self.engine.state(), TourState.WAITING_ACTION)
        self.engine.back()
        self.assertEqual(self.engine.current_step().step_id, "fallback")

    def test_tc157_cancel_cleanup(self):
        self.assertTrue(self.engine.start("test_guide")); old_request = self.navigation.requests[-1]
        self.engine.cancel("TEST_REASON")
        self.assertFalse(self.engine.is_running())
        self.assertEqual(self.engine.state(), TourState.CANCELLED)
        self.assertEqual(self.observer.unbind_calls, 1)
        self.assertIn("HIDE_STEP", self.spotlight.history)
        self.engine.cancel("REASON_2")
        self.assertEqual(self.observer.unbind_calls, 1)
        self.engine.on_surface_ready(*old_request)
        self.assertEqual(self.engine.state(), TourState.CANCELLED)

    def test_surface_request_token_rejects_late_signal(self):
        self.assertTrue(self.engine.start("test_guide")); old_request = self.navigation.requests[-1]
        self.engine.skip_step()
        self.assertEqual(self.engine.current_step().step_id, "skip")
        self.assertEqual(self.engine.state(), TourState.PREPARING_SURFACE)
        self.engine.on_surface_ready(*old_request)
        self.assertEqual(self.engine.current_step().step_id, "skip")
        self.assertEqual(self.engine.state(), TourState.PREPARING_SURFACE)

    def test_surface_failure_recovery_retry_restarts_navigation(self):
        self.assertTrue(self.engine.start("test_guide"))
        failed_request = self.navigation.requests[-1]
        self.engine.on_surface_failed(*failed_request, "timeout")
        self.assertEqual(self.engine.state(), TourState.RECOVERING)

        self.engine.retry()
        self.assertEqual(self.engine.state(), TourState.PREPARING_SURFACE)
        self.assertNotEqual(self.navigation.requests[-1], failed_request)

    def test_start_rejects_failed_precondition(self):
        guide = self.catalog.get_guide("test_guide")
        blocked = TourDefinition(guide.schema_version, "blocked", guide.content_version, guide.title,
                                 guide.category, guide.estimated_minutes, guide.steps,
                                 preconditions=("BLOCKED",))
        blocked_catalog = FakeCatalog({"blocked": blocked})
        blocked_engine = self._new_engine(blocked_catalog, TourEnvironment(lambda _: False))
        self.assertFalse(blocked_engine.start("blocked"))
        self.assertEqual(blocked_engine.state(), TourState.IDLE)

    def test_completion_persists_progress_and_allows_new_session(self):
        self.assertTrue(self.engine.start("test_guide")); self._ready()
        self.engine.skip_step(); self._ready(); self.engine.next()
        self.engine.skip_step(); self.engine.next()
        self.assertEqual(self.engine.state(), TourState.COMPLETED)
        self.assertEqual(self.progress.completed, [("test_guide", 1)])
        self.assertTrue(self.engine.start("test_guide"))


class TestTourEngineA5Async(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    def setUp(self):
        self.spotlight = FakeSpotlight(); self.registry = FakeAnchorRegistry()
        self.observer = FakeObserver(); self.navigation = FakeNavigation()
        self.dialog = FakeDialogObserver()
        guide = TourDefinition(
            schema_version=1, guide_id="a5_guide", content_version=1,
            title="A5", category="test", estimated_minutes=1,
            steps=(
                TourStep("action", TourStepType.ACTION, CalloutSpec("T1", "B1"),
                         SafetySpec(False), surface=SurfaceSpec("dash"), anchor="btn1",
                         target_policy=TargetPolicy.REQUIRED, interaction=InteractionSpec("CLICK")),
                TourStep("info", TourStepType.INFO, CalloutSpec("T2", "B2"),
                         SafetySpec(True), anchor="btn2", target_policy=TargetPolicy.SKIP),
            ),
        )
        self.engine = TourEngine(
            catalog=FakeCatalog({"a5_guide": guide}), anchor_registry=self.registry,
            navigation=self.navigation, interaction_observer=self.observer,
            spotlight=self.spotlight, dialog_observer=self.dialog, progress_store=None,
            environment=TourEnvironment(lambda _: True), navigation_timeout_ms=10,
            target_settle_timeout_ms=10,
        )

    def _run_loop(self, duration_ms=20):
        loop = QEventLoop()
        QTimer.singleShot(duration_ms, loop.quit)
        loop.exec()

    def test_tc145_stale_navigation_token(self):
        self.assertTrue(self.engine.start("a5_guide"))
        session_id, generation, request_id = self.navigation.requests[-1]
        self.engine.on_surface_ready("wrong_session", generation, request_id)
        self.engine.on_surface_ready(session_id, generation, "wrong_request")
        self.assertEqual(self.engine.state(), TourState.PREPARING_SURFACE)

    def test_tc146_navigation_watchdog(self):
        self.assertTrue(self.engine.start("a5_guide"))
        self._run_loop()
        self.assertEqual(self.engine.state(), TourState.RECOVERING)
        self.assertEqual(self.navigation.cancel_pending_calls, 1)

    def test_tc152_tc153_queued_action_advance_ordering(self):
        event_log = []
        original_unbind = self.observer.unbind
        original_hide = self.spotlight.hide_step
        self.observer.unbind = lambda: (event_log.append("unbind"), original_unbind())[1]
        self.spotlight.hide_step = lambda: (event_log.append("hide_step"), original_hide())[1]
        self.engine.state_changed.connect(lambda state: event_log.append(f"state:{state}"))

        self.assertTrue(self.engine.start("a5_guide"))
        self.engine.on_surface_ready(*self.navigation.requests[-1])
        event_log.clear()
        action_token = self.observer.binding
        self.engine.on_action_satisfied(*action_token)

        self.assertEqual(event_log[0], "unbind")
        self.assertEqual(event_log[1], f"state:{TourState.ADVANCING_STEP}")
        self.assertIn("hide_step", event_log)
        self.assertFalse(self.observer.is_bound())
        self.assertEqual(self.engine.current_step().step_id, "action")

        self.registry.status = AnchorStatus.NOT_FOUND
        loop = QEventLoop()
        self.engine.state_changed.connect(
            lambda state: loop.quit() if state is TourState.COMPLETED else None
        )
        QTimer.singleShot(1000, loop.quit)
        loop.exec()
        self.assertEqual(self.engine.state(), TourState.COMPLETED)

    def test_tc154_stale_action_callback(self):
        self.assertTrue(self.engine.start("a5_guide"))
        self.engine.on_surface_ready(*self.navigation.requests[-1])
        old_token = self.observer.binding
        self.engine.cancel()
        self.engine.on_action_satisfied(*old_token)
        self.assertEqual(self.engine.state(), TourState.CANCELLED)

    def test_target_settle_retries_before_missing_policy(self):
        self.registry.status = AnchorStatus.NOT_FOUND
        self.assertTrue(self.engine.start("a5_guide"))
        self.engine.on_surface_ready(*self.navigation.requests[-1])
        self.assertEqual(self.engine.state(), TourState.RESOLVING_TARGET)
        self._run_loop()
        self.assertEqual(self.engine.state(), TourState.RECOVERING)

    def test_target_lost_reuses_missing_target_policy(self):
        self.assertTrue(self.engine.start("a5_guide"))
        self.engine.on_surface_ready(*self.navigation.requests[-1])
        self.assertEqual(self.engine.state(), TourState.WAITING_ACTION)
        self.engine.on_target_lost(*self.observer.binding, "closed")
        self.assertEqual(self.engine.state(), TourState.RECOVERING)


if __name__ == "__main__": unittest.main()
