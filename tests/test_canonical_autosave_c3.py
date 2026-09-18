import unittest
from unittest.mock import patch

from tests.test_canonical_autosave import FakeScheduler, FakeTracker

from core.recovery.canonical_save_coordinator import CanonicalSaveCoordinator


class CanonicalAutosaveC3Tests(unittest.TestCase):
    def setUp(self):
        self.scheduler = FakeScheduler()
        self.tracker = FakeTracker()
        self.calls = []
        self.outcomes = []

        def save(**kwargs):
            self.calls.append(kwargs)
            result = self.outcomes.pop(0) if self.outcomes else True
            if result:
                self.tracker.last_saved_revision = kwargs["target_revision"]
                self.tracker.is_dirty = False
            return result

        self.save = save
        self.coordinator = CanonicalSaveCoordinator(
            revision_tracker=self.tracker,
            save_current_project=self.save,
            scheduler=self.scheduler,
            active_project_provider=lambda: object(),
        )
        self.coordinator.start()
        self.addCleanup(self.coordinator.dispose)

    def _require_status_api(self):
        self.assertTrue(
            hasattr(self.coordinator, "status_text"),
            "CanonicalSaveCoordinator must expose status_text()",
        )
        self.assertTrue(
            hasattr(self.coordinator, "countdown_text"),
            "CanonicalSaveCoordinator must expose countdown_text()",
        )

    def test_CS01_default_enabled(self):
        self.assertTrue(self.coordinator.enabled)

    def test_CS02_default_delay(self):
        self.assertEqual(self.coordinator.delay_ms, 1000)

    def test_CS05_runtime_toggle_updates_coordinator(self):
        self.coordinator.set_enabled(False)
        self.assertFalse(self.coordinator.enabled)
        self.coordinator.set_enabled(True)
        self.assertTrue(self.coordinator.enabled)

    def test_CS06_delay_change_rearms_pending_debounce(self):
        self.tracker.edit()
        self.coordinator.set_delay_ms(2000)
        self.scheduler.advance(1999)
        self.assertEqual(self.calls, [])
        self.scheduler.advance(1)
        self.assertEqual(len(self.calls), 1)

    def test_ST01_clean_project_is_saved(self):
        self._require_status_api()
        self.assertEqual(self.coordinator.status_text(), "Saved")

    def test_ST02_mutation_is_unsaved_with_countdown(self):
        self._require_status_api()
        self.tracker.edit()
        self.assertEqual(self.coordinator.status_text(), "Unsaved")
        self.assertIn("Save in", self.coordinator.countdown_text())

    def test_ST03_debounce_execution_is_saving(self):
        self._require_status_api()
        states = []

        def save_while_visible(**kwargs):
            states.append(self.coordinator.status_text())
            self.tracker.last_saved_revision = kwargs["target_revision"]
            self.tracker.is_dirty = False
            return True

        self.coordinator.save_current_project = save_while_visible
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(states, ["Saving…"])

    def test_ST04_successful_save_is_saved(self):
        self._require_status_api()
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(self.coordinator.status_text(), "Saved")

    def test_ST05_failed_save_is_failed(self):
        self._require_status_api()
        self.outcomes = [False]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(self.coordinator.status_text(), "Save failed")

    def test_ST06_revision_race_does_not_show_saved(self):
        self._require_status_api()
        def save_with_new_edit(**kwargs):
            self.calls.append(kwargs)
            self.tracker.edit()
            return True

        self.coordinator.save_current_project = save_with_new_edit
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertNotEqual(self.coordinator.status_text(), "Saved")

    def test_ST08_auto_save_off_is_unsaved_without_countdown(self):
        self._require_status_api()
        self.coordinator.set_enabled(False)
        self.tracker.edit()
        self.assertEqual(self.coordinator.status_text(), "Unsaved")
        self.assertEqual(self.coordinator.countdown_text(), "")

    def test_ST09_recovered_baseline_has_no_countdown(self):
        self._require_status_api()
        self.tracker.restore(10)
        self.assertEqual(self.coordinator.status_text(), "Unsaved")
        self.assertEqual(self.coordinator.countdown_text(), "")

    def test_RT01_first_failure_schedules_one_retry_after_five_seconds(self):
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(len(self.calls), 1)
        self.scheduler.advance(4999)
        self.assertEqual(len(self.calls), 1)
        self.scheduler.advance(1)
        self.assertEqual(len(self.calls), 2)

    def test_RT02_retry_success_finishes_cycle(self):
        self._require_status_api()
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(6000)
        self.assertEqual(self.coordinator.status_text(), "Saved")

    def test_RT03_retry_failure_stops_after_two_attempts(self):
        self.outcomes = [False, False]
        self.tracker.edit()
        self.scheduler.advance(6000)
        self.scheduler.advance(6000)
        self.assertEqual(len(self.calls), 2)

    def test_RT05_new_mutation_after_exhaustion_starts_fresh_cycle(self):
        self.outcomes = [False, False, True]
        self.tracker.edit()
        self.scheduler.advance(6000)
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertEqual(len(self.calls), 3)

    def test_RT06_new_mutation_cancels_stale_retry(self):
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.scheduler.advance(5000)
        self.assertEqual(len(self.calls), 2)

    def test_RT07_manual_save_success_cancels_retry(self):
        self.outcomes = [False]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.tracker.is_dirty = False
        self.coordinator.manual_save_succeeded()
        self.scheduler.advance(5000)
        self.assertEqual(len(self.calls), 1)

    def test_RT08_lifecycle_flush_supersedes_retry(self):
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.assertTrue(self.coordinator.flush_now())
        self.scheduler.advance(5000)
        self.assertEqual(len(self.calls), 2)

    def test_RT09_auto_save_off_cancels_retry(self):
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(1000)
        self.coordinator.set_enabled(False)
        self.scheduler.advance(5000)
        self.assertEqual(len(self.calls), 1)

    def test_RT10_project_change_prevents_stale_retry(self):
        active = [object()]
        self.coordinator.active_project_provider = lambda: active[0]
        self.outcomes = [False, True]
        self.tracker.edit()
        self.scheduler.advance(1000)
        active[0] = None
        self.coordinator.cancel_pending()
        self.scheduler.advance(5000)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
