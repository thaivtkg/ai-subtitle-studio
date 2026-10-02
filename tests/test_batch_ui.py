import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import sys

from core.batch.batch_models import BatchJob, BatchSession, BatchStatus
from ui.batch.batch_setup_dialog import BatchSetupDialog
from ui.batch.batch_progress_dashboard import BatchProgressDashboard, BatchJobRow

if not QApplication.instance():
    app = QApplication(sys.argv)

class TestBatchSetupDialog(unittest.TestCase):
    def test_dialog_creates_session_on_accept(self):
        files = ["/tmp/a.mp4", "/tmp/b.mkv", "/tmp/c.avi"]
        dialog = BatchSetupDialog(files)
        
        # Verify file list populated
        self.assertEqual(dialog.file_list.count(), 3)
        
        # Simulate start by calling internal method
        dialog._on_start()
        
        session = dialog.result_session
        self.assertIsNotNone(session)
        self.assertEqual(len(session.jobs), 3)
        self.assertEqual(session.model_size, "large-v3")
        self.assertEqual(session.output_format, "srt")


class TestBatchProgressDashboard(unittest.TestCase):
    def test_dashboard_creates_rows_and_updates(self):
        from unittest.mock import MagicMock
        
        job1 = BatchJob(id="j1", input_file="/tmp/test.mp4")
        job2 = BatchJob(id="j2", input_file="/tmp/test2.mp4")
        session = BatchSession("s1", "tiny", "en", "srt", [job1, job2])
        
        mock_manager = MagicMock()
        mock_manager.job_status_changed = MagicMock()
        mock_manager.job_progress_updated = MagicMock()
        mock_manager.session_completed = MagicMock()
        
        # BatchProgressDashboard connects signals in __init__, so mock .connect
        mock_manager.job_status_changed.connect = MagicMock()
        mock_manager.job_progress_updated.connect = MagicMock()
        mock_manager.session_completed.connect = MagicMock()
        
        dashboard = BatchProgressDashboard(session, mock_manager)
        
        self.assertEqual(len(dashboard.job_rows), 2)
        self.assertIn("j1", dashboard.job_rows)
        self.assertIn("j2", dashboard.job_rows)
        
        # Simulate status change
        dashboard._on_status_changed("j1", BatchStatus.TRANSLATING)
        row = dashboard.job_rows["j1"]
        self.assertEqual(row.status_label.text(), "TRANSLATING")
        
        # Simulate progress
        dashboard._on_progress_updated("j1", 75)
        self.assertEqual(row.progress_bar.value(), 75)
        
        # Simulate completion
        job1.status = BatchStatus.COMPLETED
        job2.status = BatchStatus.COMPLETED
        dashboard._on_session_completed()
        self.assertIn("2 succeeded", dashboard.summary_label.text())


class TestBatchJobRow(unittest.TestCase):
    def test_row_status_colors(self):
        row = BatchJobRow("test", "file.mp4")
        row.update_status(BatchStatus.EXTRACTING)
        self.assertEqual(row.status_label.text(), "EXTRACTING")
        
        row.update_status(BatchStatus.FAILED)
        self.assertEqual(row.status_label.text(), "FAILED")


if __name__ == '__main__':
    unittest.main()
