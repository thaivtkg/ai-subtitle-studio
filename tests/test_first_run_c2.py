import unittest

from core.help.first_run_policy import FirstRunDecision, evaluate_startup
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus


class FakeProgressStore:
    def __init__(self, status: GuideProgressStatus = GuideProgressStatus.NOT_STARTED):
        self._status = status
        self.dismissed_called = False

    def status(self, guide_id: str, version: int = 1) -> GuideProgress:
        return GuideProgress(self._status)

    def mark_dismissed(self, guide_id: str) -> None:
        self.dismissed_called = True


class TestC2FirstRunPolicy(unittest.TestCase):
    def test_tc178_clean_launch_prompts_banner_not_auto_start(self):
        store = FakeProgressStore(GuideProgressStatus.NOT_STARTED)
        decision = evaluate_startup(store, "getting_started")

        self.assertEqual(decision, FirstRunDecision.SHOW_BANNER)

    def test_tc181_dismissed_tour_suppresses_banner(self):
        store = FakeProgressStore(GuideProgressStatus.DISMISSED)
        decision = evaluate_startup(store, "getting_started")

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)

    def test_tc182_completed_tour_suppresses_banner(self):
        store = FakeProgressStore(GuideProgressStatus.COMPLETED)
        decision = evaluate_startup(store, "getting_started")

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)

    def test_unknown_progress_suppresses_banner_gracefully(self):
        store = FakeProgressStore(GuideProgressStatus.UNKNOWN)
        decision = evaluate_startup(store, "getting_started")

        self.assertEqual(decision, FirstRunDecision.DO_NOTHING)


if __name__ == "__main__":
    unittest.main()
