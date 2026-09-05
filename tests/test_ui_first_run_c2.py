import sys
import unittest

from PySide6.QtWidgets import QApplication

from core.tutorial.progress_store import GuideProgress, GuideProgressStatus
from ui.help.first_run_banner import FirstRunBanner
from ui.help.first_run_controller import FirstRunController


class FakeProgressStore:
    def __init__(self, status=GuideProgressStatus.NOT_STARTED):
        self._status = status
        self.dismissed_id = None
        self.completed_id = None

    def status(self, guide_id: str, version: int = 1):
        return GuideProgress(self._status)

    def mark_dismissed(self, guide_id: str, version: int = 1):
        self.dismissed_id = guide_id

    def mark_completed(self, guide_id: str, version: int = 1):
        self.completed_id = guide_id


class SpyTourEngine:
    def __init__(self):
        self.started_guide = None

    def start(self, guide_id: str) -> bool:
        self.started_guide = guide_id
        return True


class TestC2FirstRunUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.store = FakeProgressStore()
        self.engine = SpyTourEngine()
        self.banner = FirstRunBanner()
        self.controller = FirstRunController(
            progress_store=self.store,
            engine=self.engine,
            banner=self.banner,
            target_guide_id="getting_started",
        )

    def tearDown(self):
        self.banner.deleteLater()
        self.app.processEvents()

    def test_tc178_clean_interactive_launch_shows_banner_but_no_auto_start(self):
        self.controller.evaluate_and_show(
            external_open=False, recovery=False, workflow_started=False
        )

        self.assertTrue(self.banner.isVisible())
        self.assertIsNone(self.engine.started_guide)

    def test_tc179_external_open_startup_hides_banner_and_no_mutate(self):
        self.controller.evaluate_and_show(external_open=True)

        self.assertFalse(self.banner.isVisible())
        self.assertIsNone(self.store.dismissed_id)

    def test_tc180_recovery_startup_hides_banner_and_no_mutate(self):
        self.controller.evaluate_and_show(recovery=True)

        self.assertFalse(self.banner.isVisible())
        self.assertIsNone(self.store.dismissed_id)

    def test_tc181_dismiss_click_hides_banner_and_persists(self):
        self.controller.evaluate_and_show()
        self.assertTrue(self.banner.isVisible())

        self.banner.dismiss_btn.click()

        self.assertEqual(self.store.dismissed_id, "getting_started")
        self.assertFalse(self.banner.isVisible())

    def test_tc182_start_click_dismisses_first_then_starts_tour(self):
        self.controller.evaluate_and_show()

        self.banner.start_btn.click()

        self.assertEqual(self.store.dismissed_id, "getting_started")
        self.assertFalse(self.banner.isVisible())
        self.assertEqual(self.engine.started_guide, "getting_started")
        self.assertIsNone(self.store.completed_id)

    def test_tc183_workflow_started_hides_banner_without_mutation(self):
        self.controller.evaluate_and_show()
        self.assertTrue(self.banner.isVisible())

        self.controller.on_workflow_started()

        self.assertFalse(self.banner.isVisible())
        self.assertIsNone(self.store.dismissed_id)


if __name__ == "__main__":
    unittest.main()
