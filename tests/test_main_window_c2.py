import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from core.media_import.media_import_models import MediaImportResult
from core.tutorial.progress_store import GuideProgressStatus
from ui.Gui import MainWindow
from ui.help.first_run_banner import FirstRunBanner
from ui.help.first_run_controller import FirstRunController


class TestMainWindowFirstRunIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.progress_dir = tempfile.TemporaryDirectory()
        progress_file = Path(self.progress_dir.name) / "tutorial_progress.json"
        with patch("ui.Gui.RuntimePaths.get_tutorial_progress_file", return_value=progress_file):
            self.window = MainWindow(
                project_service=MagicMock(), media_import_service=MagicMock()
            )
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.progress_dir.cleanup()

    def _integration_objects(self):
        banner = getattr(self.window, "first_run_banner", None)
        controller = getattr(self.window, "first_run_controller", None)
        self.assertIsInstance(banner, FirstRunBanner)
        self.assertIsInstance(controller, FirstRunController)
        return banner, controller

    def _guide_identity(self):
        self.window.tour_catalog.load_all()
        guide = self.window.tour_catalog.get_guide("getting_started")
        self.assertIsNotNone(guide)
        return guide.guide_id, guide.content_version

    def test_tc178_clean_startup_shows_banner_without_starting_tour(self):
        banner, _ = self._integration_objects()
        self.assertTrue(banner.isVisible())
        self.assertEqual(
            self.window.tour_progress_store.status(
                *self._guide_identity()
            ).status,
            GuideProgressStatus.NOT_STARTED,
        )
        self.assertFalse(self.window.tour_engine.is_running())

    def test_tc179_external_open_suppresses_banner_without_mutation(self):
        banner, controller = self._integration_objects()
        self.assertTrue(banner.isVisible())
        controller.evaluate_and_show(external_open=True)
        self.assertTrue(banner.isHidden())
        self.assertEqual(
            self.window.tour_progress_store.status(
                *self._guide_identity()
            ).status,
            GuideProgressStatus.NOT_STARTED,
        )

    def test_tc180_recovery_suppresses_onboarding(self):
        banner, controller = self._integration_objects()
        self.assertTrue(banner.isVisible())
        controller.evaluate_and_show(recovery=True)
        self.assertTrue(banner.isHidden())
        self.assertEqual(
            self.window.tour_progress_store.status(
                *self._guide_identity()
            ).status,
            GuideProgressStatus.NOT_STARTED,
        )

    def test_tc181_dismiss_persists_catalog_identity_without_starting_tour(self):
        banner, _ = self._integration_objects()
        guide_id, content_version = self._guide_identity()
        self.window.tour_engine.start = MagicMock()
        banner.dismiss_btn.click()
        progress = self.window.tour_progress_store.status(guide_id, content_version)
        self.assertTrue(banner.isHidden())
        self.assertEqual(progress.status, GuideProgressStatus.DISMISSED)
        self.assertFalse(self.window.tour_engine.start.called)

    def test_tc182_start_persists_dismissal_before_start_without_completion_write(self):
        banner, _ = self._integration_objects()
        guide_id, content_version = self._guide_identity()
        events = []
        original_mark_dismissed = self.window.tour_progress_store.mark_dismissed

        def mark_dismissed(*args):
            events.append(("dismissed", *args))
            return original_mark_dismissed(*args)

        self.window.tour_progress_store.mark_dismissed = mark_dismissed
        self.window.tour_engine.start = lambda started_id: (
            events.append(("start", started_id)) or True
        )
        self.window.tour_progress_store.mark_completed = MagicMock()

        banner.start_btn.click()

        self.assertEqual(events, [("dismissed", guide_id, content_version), ("start", guide_id)])
        self.assertTrue(banner.isHidden())
        self.window.tour_progress_store.mark_completed.assert_not_called()

    @patch("ui.Gui.MediaImportDialog")
    def test_tc183_real_workflow_suppresses_banner_without_progress_mutation(
        self, mock_dialog_cls
    ):
        banner, _ = self._integration_objects()
        guide_id, content_version = self._guide_identity()
        self.assertTrue(banner.isVisible())

        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_result.return_value = MediaImportResult(
            local_path="/tmp/source.mp4",
            original_url="https://example.com/source.mp4",
            filename="source.mp4",
            size_bytes=1,
            media_type="video/mp4",
            metadata={},
        )
        mock_dialog.get_project_data.return_value = {
            "name": "Demo",
            "bundle_path": "/tmp/Demo.ai-subtitle",
            "media_dir": "/tmp/Demo.ai-subtitle/media",
        }
        mock_dialog_cls.return_value = mock_dialog
        self.window.tour_engine.start = MagicMock()

        with patch.object(self.window, "_switch_recovery_session"), \
                patch.object(self.window.workspace_service, "restore_workspace"), \
                patch.object(self.window.generation_panel, "check_resumable_state"), \
                patch.object(self.window, "_refresh_transcription_context_views"), \
                patch.object(self.window.revision_tracker, "reset_for_new_document"):
            self.window.action_new_from_url.trigger()

        self.assertTrue(banner.isHidden())
        self.assertEqual(
            self.window.tour_progress_store.status(guide_id, content_version).status,
            GuideProgressStatus.NOT_STARTED,
        )
        self.assertFalse(self.window.tour_engine.start.called)


if __name__ == "__main__":
    unittest.main()
