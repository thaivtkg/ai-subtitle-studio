import unittest

from core.help.first_run_policy import (
    FirstRunDecision,
    complete_first_run,
    dismiss_first_run,
    evaluate_startup,
    start_first_run,
)
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus


class FakeProgressStore:
    def __init__(self, status: GuideProgressStatus = GuideProgressStatus.NOT_STARTED):
        self._status = status
        self.events = []

    def status(self, guide_id: str, version: int = 1) -> GuideProgress:
        return GuideProgress(self._status)

    def mark_dismissed(self, guide_id: str, content_version: int) -> None:
        self.events.append(("dismissed", guide_id, content_version))
        self._status = GuideProgressStatus.DISMISSED

    def mark_completed(self, guide_id: str, content_version: int) -> None:
        self.events.append(("completed", guide_id, content_version))
        self._status = GuideProgressStatus.COMPLETED


class TestC2FirstRunPolicy(unittest.TestCase):
    def test_tc178_clean_launch_prompts_banner_not_auto_start(self):
        store = FakeProgressStore()
        started = []
        decision = evaluate_startup(store, "getting_started", content_version=2)

        self.assertEqual(decision, FirstRunDecision.SHOW_BANNER)
        self.assertEqual(started, [])
        self.assertEqual(store.events, [])

    def test_tc179_external_open_suppresses_without_dismissal(self):
        store = FakeProgressStore()
        decision = evaluate_startup(
            store, "getting_started", content_version=2, external_open=True
        )

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)
        self.assertEqual(store.events, [])

    def test_tc180_recovery_suppresses_without_mutation(self):
        store = FakeProgressStore()
        decision = evaluate_startup(
            store, "getting_started", content_version=2, recovery=True
        )

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)
        self.assertEqual(store.events, [])

    def test_tc181_explicit_dismiss_persists_dismissed_without_start(self):
        store = FakeProgressStore()

        dismiss_first_run(store, "getting_started", 2)

        self.assertEqual(store.events, [("dismissed", "getting_started", 2)])
        self.assertEqual(store.status("getting_started", 2).status, GuideProgressStatus.DISMISSED)

    def test_tc182_start_persists_dismissed_before_tour_and_complete_overwrites(self):
        store = FakeProgressStore()

        def start_tour(_guide_id):
            store.events.append(("start",))
            return True

        self.assertTrue(start_first_run(store, "getting_started", 2, start_tour))
        self.assertEqual(store.events, [("dismissed", "getting_started", 2), ("start",)])

        complete_first_run(store, "getting_started", 2)
        self.assertEqual(store.events[-1], ("completed", "getting_started", 2))
        self.assertEqual(store.status("getting_started", 2).status, GuideProgressStatus.COMPLETED)

    def test_tc183_workflow_hides_banner_without_progress_mutation(self):
        store = FakeProgressStore()
        decision = evaluate_startup(
            store, "getting_started", content_version=2, workflow_started=True
        )

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)
        self.assertEqual(store.events, [])

    def test_unknown_progress_suppresses_banner_gracefully(self):
        store = FakeProgressStore(GuideProgressStatus.UNKNOWN)
        decision = evaluate_startup(store, "getting_started", content_version=2)

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)


if __name__ == "__main__":
    unittest.main()
