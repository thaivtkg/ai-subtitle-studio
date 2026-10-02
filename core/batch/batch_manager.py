from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable
from typing import Optional
from core.batch.batch_models import BatchSession, BatchJob, BatchStatus

class BatchWorker(QRunnable):
    def __init__(self, manager: 'BatchManager'):
        super().__init__()
        self.manager = manager

    def run(self):
        if not self.manager.current_session:
            return
            
        for job in self.manager.current_session.jobs:
            if job.status in (BatchStatus.COMPLETED, BatchStatus.FAILED):
                continue
                
            self.manager._update_job_status(job, BatchStatus.EXTRACTING)
            # In Gate 2, we just simulate the start of the job. 
            # Real loop happens in Gate 3.
            break

class BatchManager(QObject):
    session_started = Signal(object) # BatchSession
    job_status_changed = Signal(str, object) # job_id, BatchStatus
    job_progress_updated = Signal(str, int) # job_id, progress
    session_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_session: Optional[BatchSession] = None
        self.thread_pool = QThreadPool.globalInstance()

    def start_session(self, session: BatchSession):
        self.current_session = session
        self.session_started.emit(session)
        
        worker = BatchWorker(self)
        self.thread_pool.start(worker)

    def _update_job_status(self, job: BatchJob, status: BatchStatus):
        job.status = status
        self.job_status_changed.emit(job.id, status)
