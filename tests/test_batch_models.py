import json
import unittest
from core.batch.batch_models import BatchStatus, BatchJob, BatchSession

class TestBatchModels(unittest.TestCase):
    def test_batch_job_serialization(self):
        job = BatchJob(
            id="job_1",
            input_file="test.mp4",
            status=BatchStatus.PENDING,
            progress=0.0
        )
        data = job.to_dict()
        self.assertEqual(data['status'], 'PENDING')
        
        job2 = BatchJob.from_dict(data)
        self.assertEqual(job2.id, "job_1")
        self.assertEqual(job2.status, BatchStatus.PENDING)

    def test_batch_session_serialization(self):
        job = BatchJob(id="job_1", input_file="test.mp4", status=BatchStatus.EXTRACTING, progress=50.0)
        session = BatchSession(
            session_id="session_1",
            model_size="large-v3",
            target_lang="vi",
            output_format="srt",
            jobs=[job]
        )
        data = session.to_dict()
        self.assertEqual(data['jobs'][0]['status'], 'EXTRACTING')
        
        session2 = BatchSession.from_dict(data)
        self.assertEqual(len(session2.jobs), 1)
        self.assertEqual(session2.jobs[0].status, BatchStatus.EXTRACTING)

if __name__ == '__main__':
    unittest.main()
