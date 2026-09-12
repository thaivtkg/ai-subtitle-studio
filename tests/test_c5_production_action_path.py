import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.tutorial.models import TourState
from ui.Gui import MainWindow


class TestC5ProductionActionPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow(
            project_service=MagicMock(),
            media_import_service=MagicMock(),
        )
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def _wait_until(self, predicate, timeout_ms=1500):
        for _ in range(timeout_ms // 10):
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        self.fail("Timed out waiting for production tour state")

    def _advance_info_step(self, step_id):
        self._wait_until(
            lambda: (
                self.window.tour_engine.current_step() is not None
                and self.window.tour_engine.current_step().step_id == step_id
                and self.window.tour_engine.state() is TourState.SHOWING_INFO
            )
        )
        self.window.tour_engine.next()
        self.app.processEvents()

    def test_real_click_advances_production_action_and_navigates(self):
        self.assertTrue(self.window.tour_engine.start("getting_started"))

        self._advance_info_step("welcome")
        self._advance_info_step("dashboard_overview")
        self._advance_info_step("create_project_entry")

        self._wait_until(
            lambda: (
                self.window.tour_engine.current_step() is not None
                and self.window.tour_engine.current_step().step_id
                == "open_video_workspace"
                and self.window.tour_engine.state() is TourState.WAITING_ACTION
            )
        )

        QTest.mouseClick(self.window.nav_btns[1], Qt.MouseButton.LeftButton)
        self._wait_until(
            lambda: (
                self.window._active_nav_index == 1
                and self.window.tour_engine.current_step() is not None
                and self.window.tour_engine.current_step().step_id
                == "subtitle_editor_overview"
            )
        )
        self.assertEqual(self.window._active_nav_index, 1)
        self.assertEqual(
            self.window.tour_engine.current_step().step_id,
            "subtitle_editor_overview",
        )


if __name__ == "__main__":
    unittest.main()
