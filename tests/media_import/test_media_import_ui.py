import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.media_import.media_import_models import MediaImportProgress, MediaImportStage

try:
    from ui.dialogs.media_import_dialog import MediaImportDialog, MediaImportDialogState
except (ModuleNotFoundError, ImportError):
    MediaImportDialog = None
    MediaImportDialogState = None


class TestMediaImportUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MediaImportDialog is None:
            raise unittest.SkipTest("SUT UI/Worker not implemented")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.mock_service = MagicMock()
        self.dialog = MediaImportDialog(self.mock_service, mode="queue")

    def test_full_transition_and_worker_success(self):
        self.assertEqual(self.dialog.current_state, MediaImportDialogState.IDLE)
        self.dialog.url_input.setText("https://example.com/video")

        with patch("ui.dialogs.media_import_dialog.MediaImportWorker") as worker_cls:
            worker = MagicMock()
            worker_cls.return_value = worker
            self.dialog.import_btn.click()

            self.assertEqual(self.dialog.current_state, MediaImportDialogState.RESOLVING)
            worker.start.assert_called_once()
            self.dialog._on_progress(MediaImportProgress(MediaImportStage.DOWNLOADING, percent=50.0))
            self.assertEqual(self.dialog.current_state, MediaImportDialogState.DOWNLOADING)
            self.dialog._on_progress(MediaImportProgress(MediaImportStage.RESOLVING))
            self.assertEqual(self.dialog.current_state, MediaImportDialogState.DOWNLOADING)

            result = MagicMock()
            self.dialog._on_succeeded(result)
            self.assertIs(self.dialog.result, result)

    def test_dialog_uses_dark_theme_stylesheet(self):
        self.assertIn("QDialog", self.dialog.styleSheet())
        self.assertIn("QPushButton", self.dialog.styleSheet())

    def test_indeterminate_progress_sets_range_zero(self):
        self.dialog._set_state(MediaImportDialogState.DOWNLOADING)
        self.dialog._on_progress(MediaImportProgress(MediaImportStage.DOWNLOADING, downloaded_bytes=1024))
        self.assertEqual(self.dialog.progress_bar.minimum(), 0)
        self.assertEqual(self.dialog.progress_bar.maximum(), 0)

    def test_close_running_dialog_cancels_and_waits(self):
        self.dialog.url_input.setText("https://test")
        with patch("ui.dialogs.media_import_dialog.MediaImportWorker") as worker_cls:
            worker = MagicMock()
            worker_cls.return_value = worker
            self.dialog.import_btn.click()
            event = MagicMock()
            self.dialog.closeEvent(event)

            event.ignore.assert_called_once()
            self.assertEqual(self.dialog.current_state, MediaImportDialogState.CANCELLING)
            self.assertTrue(self.dialog._close_pending)
            worker.cancel.assert_called_once()
            with patch.object(self.dialog, "reject") as reject:
                self.dialog._on_cancelled()
                self.assertEqual(self.dialog.current_state, MediaImportDialogState.CANCELLED)
                reject.assert_not_called()
                self.dialog._on_worker_thread_finished()
                reject.assert_called_once()


if __name__ == "__main__":
    unittest.main()
