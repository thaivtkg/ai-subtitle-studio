import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from core.media_import.media_import_models import MediaImportResult

try:
    from ui.Gui import MainWindow
except (ModuleNotFoundError, ImportError):
    MainWindow = None


class TestMainWindowImportIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MainWindow is None:
            raise unittest.SkipTest("MainWindow module not found")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.mock_project_service = MagicMock()
        self.mock_media_import_service = MagicMock()
        self.window = MainWindow(
            project_service=self.mock_project_service,
            media_import_service=self.mock_media_import_service,
        )

    @patch("ui.Gui.MediaImportDialog")
    def test_new_from_url_action_creates_project_on_accepted(self, mock_dialog_cls):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        fake_result = MediaImportResult(
            local_path="/tmp/media_imports/abc/source.mp4",
            original_url="https://example.com/video.mp4",
            filename="source.mp4",
            size_bytes=1024,
            media_type="video/mp4",
            metadata={},
        )
        mock_dialog.get_result.return_value = fake_result
        mock_dialog_cls.return_value = mock_dialog

        self.assertTrue(hasattr(self.window, "action_new_from_url"))
        mock_dialog.get_project_data.return_value = {
            "name": "Demo",
            "bundle_path": "/tmp/Demo.ai-subtitle",
            "media_dir": "/tmp/Demo.ai-subtitle/media",
        }
        with patch.object(self.window, "_switch_recovery_session"), \
                patch.object(self.window.workspace_service, "restore_workspace"), \
                patch.object(self.window.generation_panel, "check_resumable_state"), \
                patch.object(self.window, "_refresh_transcription_context_views"), \
                patch.object(self.window.revision_tracker, "reset_for_new_document"):
            self.window.action_new_from_url.trigger()

        mock_dialog_cls.assert_called_once_with(
            self.mock_media_import_service, self.window, mode="new_project"
        )
        mock_dialog.exec.assert_called_once()
        args = self.mock_project_service.create_project.call_args.args
        self.assertEqual(args[2], fake_result.local_path)

    @patch("ui.Gui.MediaImportDialog")
    def test_new_from_url_action_does_nothing_on_rejected(self, mock_dialog_cls):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
        mock_dialog.get_result.return_value = None
        mock_dialog_cls.return_value = mock_dialog

        self.assertTrue(hasattr(self.window, "action_new_from_url"))
        self.window.action_new_from_url.trigger()

        self.mock_project_service.create_project.assert_not_called()


if __name__ == "__main__":
    unittest.main()
