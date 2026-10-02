import unittest
from unittest.mock import MagicMock
from PySide6.QtCore import QCoreApplication
import sys

from core.batch.batch_models import BatchJob, BatchSession, BatchStatus
from core.batch.batch_manager import BatchManager

# Ensure QApplication exists for Qt Signals
if not QCoreApplication.instance():
    app = QCoreApplication(sys.argv)

class TestBatchManager(unittest.TestCase):
    def setUp(self):
        self.manager = BatchManager()
        self.job = BatchJob(id="job_1", input_file="test.mp4")
        self.session = BatchSession(
            session_id="session_1",
            model_size="tiny",
            target_lang="en",
            output_format="srt",
            jobs=[self.job]
        )

    def test_manager_receives_session_and_emits_signals(self):
        # We use mocks to track if signals are emitted
        session_started_spy = MagicMock()
        status_changed_spy = MagicMock()
        
        self.manager.session_started.connect(session_started_spy)
        self.manager.job_status_changed.connect(status_changed_spy)

        self.manager.start_session(self.session)
        
        # Wait for the worker thread to process
        from PySide6.QtCore import QThreadPool, QCoreApplication
        QThreadPool.globalInstance().waitForDone()
        QCoreApplication.processEvents()
        
        session_started_spy.assert_called_once_with(self.session)
        # Should start processing and emit EXTRACTING
        status_changed_spy.assert_any_call("job_1", BatchStatus.EXTRACTING)

if __name__ == '__main__':
    unittest.main()
