import importlib
import unittest


class FakeScheduler:
    def __init__(self):
        self.now = 0
        self._next = 0
        self.events = {}

    def call_later(self, delay_ms, callback):
        self._next += 1
        self.events[self._next] = (self.now + delay_ms, callback)
        return self._next

    def cancel(self, handle):
        self.events.pop(handle, None)

    def advance(self, elapsed_ms):
        target = self.now + elapsed_ms
        while True:
            due = [
                (deadline, handle, callback)
                for handle, (deadline, callback) in self.events.items()
                if deadline <= target
            ]
            if not due:
                self.now = target
                return
            deadline, handle, callback = min(due)
            self.now = deadline
            self.events.pop(handle, None)
            callback()


class FakeTracker:
    def __init__(self, revision=0):
        self.edit_revision = revision
        self.snapshot_revision = revision
        self.last_saved_revision = revision
        self.recovered_dirty_baseline = False
        self.is_dirty = False
        self.revision_changed = SignalSpy()

    def edit(self):
        self.edit_revision += 1
        self.is_dirty = True
        self.revision_changed.emit(self.edit_revision)

    def restore(self, revision):
        self.edit_revision = revision
        self.snapshot_revision = revision
        self.recovered_dirty_baseline = True
        self.is_dirty = True
        self.revision_changed.emit(revision)


class SignalSpy:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        self._callbacks.remove(callback)

    def emit(self, value):
        for callback in tuple(self._callbacks):
            callback(value)


class CanonicalAutosaveContract(unittest.TestCase):
    def setUp(self):
        try:
            module = importlib.import_module("core.recovery.canonical_save_coordinator")
        except ModuleNotFoundError:
            module = None
        self.coordinator_type = getattr(module, "CanonicalSaveCoordinator", None)
        self.assertIsNotNone(
            self.coordinator_type,
            "Feature 33.1 must add CanonicalSaveCoordinator before these tests can pass",
        )
        self.scheduler = FakeScheduler()
        self.tracker = FakeTracker()
        self.saves = []

        def save_current_project(**kwargs):
            self.saves.append(kwargs)
            target_revision = kwargs["target_revision"]
            self.tracker.last_saved_revision = target_revision
            self.tracker.is_dirty = False
            return True

        self.coordinator = self.coordinator_type(
            revision_tracker=self.tracker,
            save_current_project=save_current_project,
            scheduler=self.scheduler,
            active_project_provider=lambda: object(),
            delay_ms=1000,
            enabled=True,
        )
        self.coordinator.start()
        self.addCleanup(self.coordinator.dispose)

    def test_CA01_edit_saves_once_after_debounce(self):
        self.tracker.edit()
        self.scheduler.advance(999)
        self.assertEqual(self.saves, [])
        self.scheduler.advance(1)
        self.assertEqual(len(self.saves), 1)

    def test_CA02_successful_autosave_clears_dirty(self):
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertFalse(self.tracker.is_dirty)

    def test_CA03_successful_autosave_advances_last_saved_revision(self):
        self.tracker.edit()
        revision = self.tracker.edit_revision
        self.scheduler.advance(1000)
        self.assertEqual(self.tracker.last_saved_revision, revision)

    def test_CA04_edit_burst_resets_debounce(self):
        self.tracker.edit()
        self.scheduler.advance(400)
        self.tracker.edit()
        self.scheduler.advance(599)
        self.assertEqual(self.saves, [])
        self.scheduler.advance(401)
        self.assertEqual(len(self.saves), 1)

    def test_CA05_read_only_activity_does_not_save(self):
        self.scheduler.advance(5000)
        self.assertEqual(self.saves, [])

    def test_CA06_disabled_autosave_does_not_save(self):
        self.coordinator.set_enabled(False)
        self.tracker.edit()
        self.scheduler.advance(5000)
        self.assertEqual(self.saves, [])

    def test_CA07_enabling_while_normally_dirty_schedules_save(self):
        self.coordinator.set_enabled(False)
        self.tracker.edit()
        self.coordinator.set_enabled(True)
        self.scheduler.advance(1000)
        self.assertEqual(len(self.saves), 1)

    def test_CA08_disabling_pending_save_keeps_dirty(self):
        self.tracker.edit()
        self.coordinator.set_enabled(False)
        self.scheduler.advance(5000)
        self.assertEqual(self.saves, [])
        self.assertTrue(self.tracker.is_dirty)

    def test_CA09_failed_save_keeps_dirty(self):
        self.saves.clear()
        self.coordinator.save_current_project = lambda **kwargs: False
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertTrue(self.tracker.is_dirty)

    def test_CA10_failed_save_does_not_advance_last_saved_revision(self):
        self.coordinator.save_current_project = lambda **kwargs: False
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(self.tracker.last_saved_revision, 0)

    def test_CA11_newer_revision_remains_dirty_after_older_save(self):
        def save_with_new_edit(**kwargs):
            self.tracker.edit()
            return True

        self.coordinator.save_current_project = save_with_new_edit
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertTrue(self.tracker.is_dirty)
        self.assertEqual(len(self.saves), 0)

    def test_CA13_autosave_success_does_not_request_manual_toast(self):
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertFalse(self.saves[0].get("notify_user", True))

    def test_CA14_failed_autosave_exposes_failure_state(self):
        self.coordinator.save_current_project = lambda **kwargs: False
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(self.coordinator.presentation_state, "save_failed")

    def test_CA18_recovery_snapshot_path_remains_available_after_canonical_failure(self):
        self.coordinator.save_current_project = lambda **kwargs: False
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertTrue(self.coordinator.recovery_protection_available)

    def test_CA20_success_cancels_recovery_cycle(self):
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertTrue(self.coordinator.recovery_cycle_cancelled)

    def test_CA23_manual_save_while_pending_does_not_duplicate(self):
        self.tracker.edit()
        self.tracker.is_dirty = False
        self.coordinator.manual_save_succeeded()
        self.scheduler.advance(1000)
        self.assertEqual(self.saves, [])

    def test_CA24_no_active_project_does_not_save(self):
        self.coordinator.active_project_provider = lambda: None
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(self.saves, [])

    def test_CA_R1_recovered_baseline_is_not_automatically_saved(self):
        self.tracker.restore(10)
        self.scheduler.advance(5000)
        self.assertEqual(self.saves, [])

    def test_CA_R2_new_edit_after_recovered_baseline_is_eligible(self):
        self.tracker.restore(10)
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(len(self.saves), 1)


if __name__ == "__main__":
    unittest.main()
