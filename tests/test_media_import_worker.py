import sys
import threading
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import (
    MediaImportProgress,
    MediaImportResult,
    MediaImportStage,
)

try:
    from workers.media_import_worker import MediaImportWorker
except (ModuleNotFoundError, ImportError):
    MediaImportWorker = None


class TestMediaImportWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MediaImportWorker is None:
            raise unittest.SkipTest("SUT MediaImportWorker not implemented")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.mock_service = MagicMock()
        self.url = "https://example.com/video.mp4"
        self.worker = MediaImportWorker(self.mock_service, self.url)

    def test_worker_emits_finished_signal_on_success(self):
        expected_result = MediaImportResult(
            local_path="/tmp/source.mp4",
            original_url=self.url,
            filename="source.mp4",
            size_bytes=1024,
            media_type="video/mp4",
            metadata={},
        )
        self.mock_service.import_from_url.return_value = expected_result
        emitted_results = []
        self.worker.succeeded.connect(emitted_results.append)

        self.worker.run()

        self.assertEqual(emitted_results, [expected_result])
        self.mock_service.import_from_url.assert_called_once()

    def test_worker_emits_error_signal_on_failure(self):
        expected_error = MediaImportError(
            MediaImportErrorCode.UNSUPPORTED_URL,
            "Cannot extract media",
        )
        self.mock_service.import_from_url.side_effect = expected_error
        emitted_errors = []
        self.worker.failed.connect(emitted_errors.append)

        self.worker.run()

        self.assertEqual(len(emitted_errors), 1)
        self.assertEqual(emitted_errors[0].code, MediaImportErrorCode.UNSUPPORTED_URL)

    def test_worker_routes_progress_callback_to_signal(self):
        def fake_import(url, progress_callback, cancel_flag):
            progress_callback(MediaImportProgress(stage=MediaImportStage.RESOLVING))
            progress_callback(MediaImportProgress(stage=MediaImportStage.DOWNLOADING))
            return MagicMock()

        self.mock_service.import_from_url.side_effect = fake_import
        emitted_progress = []
        self.worker.progress_changed.connect(emitted_progress.append)

        self.worker.run()

        self.assertEqual(
            [progress.stage for progress in emitted_progress],
            [MediaImportStage.RESOLVING, MediaImportStage.DOWNLOADING],
        )

    def test_worker_cancel_method_sets_threading_event(self):
        self.assertIsInstance(self.worker.cancel_flag, threading.Event)
        self.assertFalse(self.worker.cancel_flag.is_set())

        self.worker.cancel()

        self.assertTrue(self.worker.cancel_flag.is_set())
        self.mock_service.import_from_url.return_value = MagicMock()
        self.worker.run()
        self.assertEqual(
            self.mock_service.import_from_url.call_args.kwargs["cancel_flag"],
            self.worker.cancel_flag,
        )

    def test_worker_cancelled_emits_cancelled_not_failed(self):
        self.mock_service.import_from_url.side_effect = MediaImportError(
            MediaImportErrorCode.DOWNLOAD_CANCELLED, "Cancelled"
        )
        emitted_errors = []
        emitted_cancels = []
        self.worker.failed.connect(emitted_errors.append)
        self.worker.cancelled.connect(lambda: emitted_cancels.append(True))

        self.worker.run()

        self.assertEqual(emitted_errors, [])
        self.assertEqual(emitted_cancels, [True])

    def test_worker_forwards_destination_dir(self):
        destination = "/tmp/Demo.ai-subtitle/media"
        self.mock_service.import_from_url.return_value = MagicMock()
        worker = MediaImportWorker(self.mock_service, self.url, destination_dir=destination)

        worker.run()

        self.assertEqual(
            self.mock_service.import_from_url.call_args.kwargs["destination_dir"],
            destination,
        )


if __name__ == "__main__":
    unittest.main()
