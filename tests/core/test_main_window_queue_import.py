import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from core.media_import.media_import_models import MediaImportResult

try:
    from ui.Gui import MainWindow
except (ModuleNotFoundError, ImportError, OSError):
    MainWindow = None


class TestMainWindowQueueImportIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MainWindow is None:
            raise unittest.SkipTest("ui.Gui module not found")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.mock_project_service = MagicMock()
        self.mock_media_import_service = MagicMock()
        self.window = MainWindow(
            project_service=self.mock_project_service,
            media_import_service=self.mock_media_import_service,
        )
        self.window.queue_mgr = MagicMock()
        self.window.video_player = MagicMock()

    @patch("ui.Gui.MediaImportDialog")
    def test_add_url_to_queue_action_skips_project_creation_and_loads_player(self, mock_dialog_cls):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        fake_result = MediaImportResult(
            local_path="/app_data/media_imports/abc/source.mp4",
            original_url="https://example.com/video.mp4",
            filename="source.mp4",
            size_bytes=1024,
            media_type="video/mp4",
            metadata={},
        )
        mock_dialog.get_result.return_value = fake_result
        mock_dialog_cls.return_value = mock_dialog

        self.assertTrue(hasattr(self.window, "action_add_url_to_queue"))
        self.window.action_add_url_to_queue.trigger()

        mock_dialog_cls.assert_called_once_with(
            self.mock_media_import_service, self.window, mode="queue"
        )
        mock_dialog.exec.assert_called_once()
        self.mock_project_service.create_project.assert_not_called()
        self.assertIn(fake_result.local_path, self.window._queue_project_dirs)
        self.assertIsNone(self.window._queue_project_dirs[fake_result.local_path])
        self.window.queue_mgr.add_video.assert_called_once_with(fake_result.local_path)
        self.window.queue_mgr.set_active.assert_called_once_with(fake_result.local_path)
        self.window.video_player.load_video.assert_called_once_with(fake_result.local_path)


if __name__ == "__main__":
    unittest.main()
