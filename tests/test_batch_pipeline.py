import unittest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QCoreApplication, QThreadPool
import sys

from core.batch.batch_models import BatchJob, BatchSession, BatchStatus
from core.batch.batch_manager import BatchManager

if not QCoreApplication.instance():
    app = QCoreApplication(sys.argv)

class TestBatchPipeline(unittest.TestCase):
    @patch('core.batch.batch_manager.ExportService', autospec=True)
    @patch('core.batch.batch_manager.FasterWhisperService', autospec=True)
    @patch('core.batch.batch_manager.MediaImportService', autospec=True)
    def test_pipeline_handles_errors_and_continues(self, mock_import, mock_whisper, mock_export):
        manager = BatchManager()
        
        job1 = BatchJob(id="job_1", input_file="error.mp4")
        job2 = BatchJob(id="job_2", input_file="success.mp4")
        session = BatchSession("s1", "tiny", "en", "srt", [job1, job2])
        
        # Configure the mock to raise Exception on the first call (job1 translation), succeed on second
        whisper_instance = mock_whisper.return_value
        whisper_instance.run.side_effect = [Exception("Whisper Failed"), {"segments": []}]
        
        status_spy = MagicMock()
        manager.job_status_changed.connect(status_spy)
        
        manager.start_session(session)
        QThreadPool.globalInstance().waitForDone()
        QCoreApplication.processEvents()
        
        # Verify job1 failed
        self.assertEqual(session.jobs[0].status, BatchStatus.FAILED)
        self.assertEqual(session.jobs[0].error_message, "Whisper Failed")
        
        # Verify job2 completed successfully
        self.assertEqual(session.jobs[1].status, BatchStatus.COMPLETED)
        
        # Verify signals
        status_spy.assert_any_call("job_1", BatchStatus.FAILED)
        status_spy.assert_any_call("job_2", BatchStatus.COMPLETED)

if __name__ == '__main__':
    unittest.main()
