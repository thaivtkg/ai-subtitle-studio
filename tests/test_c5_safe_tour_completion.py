import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.runtime.runtime_paths import RuntimePaths
from core.tutorial.models import TourState
from core.tutorial.progress_store import GuideProgressStatus
from ui.Gui import MainWindow


class TestC5SafeTourCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_service = MagicMock()
        self.media_import_service = MagicMock()
        self.recovery_manager = MagicMock()
        progress_path = Path(self.temp_dir.name) / "tutorial_progress.json"
        with patch.object(
            RuntimePaths, "get_tutorial_progress_file", return_value=progress_path
        ):
            self.window = MainWindow(
                project_service=self.project_service,
                media_import_service=self.media_import_service,
                recovery_manager=self.recovery_manager,
            )
        self.window.show()
        self.app.processEvents()

        self.project_service.reset_mock()
        self.media_import_service.reset_mock()
        self.recovery_manager.reset_mock()
        self.window.subtitle_whisper_service.load_model = MagicMock()
        self.window.subtitle_whisper_service.transcribe_batch = MagicMock()
        self.window.subtitle_generation_service.start_generation = MagicMock()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp_dir.cleanup()

    def _wait_until(self, predicate, timeout_ms=2000):
        for _ in range(timeout_ms // 10):
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        self.fail("Timed out waiting for safe-tour state")

    def _wait_for_step(self, step_id, state):
        self._wait_until(
            lambda: (
                self.window.tour_engine.current_step() is not None
                and self.window.tour_engine.current_step().step_id == step_id
                and self.window.tour_engine.state() is state
            )
        )

    def test_full_production_tour_completes_without_business_mutation(self):
        seen_steps = []
        self.window.tour_engine.step_changed.connect(
            lambda _session, step_id, _index, _generation: seen_steps.append(step_id)
        )

        self.assertTrue(self.window.tour_engine.start("getting_started"))

        for step_id in ("welcome", "dashboard_overview", "create_project_entry"):
            self._wait_for_step(step_id, TourState.SHOWING_INFO)
            self.window.tour_engine.next()

        self._wait_for_step("open_video_workspace", TourState.WAITING_ACTION)
        QTest.mouseClick(self.window.nav_btns[1], Qt.MouseButton.LeftButton)
        self._wait_for_step("subtitle_editor_overview", TourState.SHOWING_INFO)
        self.assertEqual(self.window._active_nav_index, 1)

        self.window.tour_engine.next()
        self._wait_for_step("ai_workspace_overview", TourState.SHOWING_INFO)
        self.assertEqual(self.window.dock_tabs.currentIndex(), 0)

        self.window.tour_engine.next()
        self._wait_for_step("generation_demo", TourState.SHOWING_DEMO)

        self.window.tour_engine.next()
        self._wait_for_step("export_center_overview", TourState.SHOWING_INFO)
        self.assertEqual(self.window._active_nav_index, 5)

        self.window.tour_engine.next()
        self._wait_for_step("finish", TourState.SHOWING_INFO)
        self.window.tour_engine.next()
        self._wait_until(lambda: self.window.tour_engine.state() is TourState.COMPLETED)

        self.assertEqual(
            seen_steps,
            [
                "welcome",
                "dashboard_overview",
                "create_project_entry",
                "open_video_workspace",
                "subtitle_editor_overview",
                "ai_workspace_overview",
                "generation_demo",
                "export_center_overview",
                "finish",
            ],
        )
        self.assertEqual(
            self.window.tour_progress_store.status("getting_started", 2).status,
            GuideProgressStatus.COMPLETED,
        )

        self.assertEqual(self.project_service.method_calls, [])
        self.assertEqual(self.media_import_service.method_calls, [])
        self.assertEqual(self.recovery_manager.method_calls, [])
        self.window.subtitle_whisper_service.load_model.assert_not_called()
        self.window.subtitle_whisper_service.transcribe_batch.assert_not_called()
        self.window.subtitle_generation_service.start_generation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
