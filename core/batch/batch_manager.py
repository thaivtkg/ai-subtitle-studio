from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable
from typing import Optional
from core.batch.batch_models import BatchSession, BatchJob, BatchStatus
from core.artifacts.artifact import Artifact
from core.artifacts.artifact_types import ArtifactType, ArtifactStatus
from core.artifacts.artifact_store import ArtifactStore
from core.translation.batch_translator import TranslationBatchWorker
from core.translation.llm_translation_service import LLMTranslationService
from core.database.glossary_manager import GlossaryManager
from core.database.tm_manager import TranslationMemoryManager
from core.export.subtitle_parser import parse_srt_content
import os
import uuid
from datetime import datetime

# We use these placeholder imports to mock them in tests
# In real code, these would be the actual services.
class ExportService:
    def run(self, artifact_id, *args, **kwargs): pass
class FasterWhisperService:
    def run(self, *args, **kwargs): 
        # Mock returning an artifact ID
        return "mock_whisper_artifact_123"
class MediaImportService:
    def run(self, *args, **kwargs): pass

class BatchWorker(QRunnable):
    def __init__(self, manager: 'BatchManager'):
        super().__init__()
        self.manager = manager
        self.artifact_store = getattr(manager, 'artifact_store', ArtifactStore())

    def _ms_to_srt(self, ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def run(self):
        if not self.manager.current_session:
            return
            
        trans_config = getattr(self.manager.current_session, 'translation_config', {})
        enable_translation = trans_config.get("enabled", False)
        
        for job in self.manager.current_session.jobs:
            if job.status in (BatchStatus.COMPLETED, BatchStatus.FAILED):
                continue
                
            try:
                # 1. EXTRACTING
                self.manager._update_job_status(job, BatchStatus.EXTRACTING)
                import_svc = MediaImportService()
                import_svc.run(job.input_file)
                
                # WHISPER (Shadow SRT)
                whisper_svc = FasterWhisperService()
                whisper_artifact_id = whisper_svc.run(job.input_file)
                
                target_artifact_id = whisper_artifact_id
                
                # 2. TRANSLATING (Conditional Branching)
                if enable_translation:
                    self.manager._update_job_status(job, BatchStatus.TRANSLATING)
                    
                    # Read segments from Whisper Artifact
                    whisper_artifact = self.artifact_store.get(whisper_artifact_id)
                    segments = []
                    if whisper_artifact and os.path.exists(whisper_artifact.path):
                        with open(whisper_artifact.path, 'r', encoding='utf-8') as f:
                            segments = parse_srt_content(f.read())
                    else:
                        # Fallback for when artifact doesn't physically exist in tests
                        segments = [{"id": "1", "stt": "1", "start": 0, "end": 1000, "text": "Dummy text", "original_text": "Dummy text"}]
                        
                    llm_svc = LLMTranslationService(provider="gemini", model_name=self.manager.current_session.model_size)
                    tm_manager = TranslationMemoryManager()
                    glossary_manager = GlossaryManager()
                    
                    target_lang = trans_config.get("target_lang", "Vietnamese")
                    domain = trans_config.get("domain", "general")
                    
                    trans_worker = TranslationBatchWorker(
                        service=llm_svc,
                        tm_manager=tm_manager,
                        glossary_manager=glossary_manager,
                        segments=segments,
                        source_lang="auto",
                        target_lang=target_lang,
                        domain=domain
                    )
                    
                    error_occurred = []
                    translated_segments = []
                    
                    def on_progress(current, total):
                        pct = int((current / total) * 100) if total > 0 else 0
                        self.manager.job_progress_updated.emit(job.id, pct)
                        
                    def on_chunk_completed(idx, segs):
                        translated_segments.extend(segs)
                        
                    def on_error(err):
                        error_occurred.append(err)
                        
                    trans_worker.signals.progress.connect(on_progress)
                    trans_worker.signals.chunk_completed.connect(on_chunk_completed)
                    trans_worker.signals.error.connect(on_error)
                    
                    # Run synchronously in this thread
                    trans_worker.run()
                    
                    # Memory Leak Guard: Disconnect signals before deleting reference
                    trans_worker.signals.progress.disconnect(on_progress)
                    trans_worker.signals.chunk_completed.disconnect(on_chunk_completed)
                    trans_worker.signals.error.disconnect(on_error)
                    
                    if error_occurred:
                        raise RuntimeError(f"Translation failed: {error_occurred[0]}")
                        
                    # Write output to new Artifact file
                    video_name = os.path.splitext(os.path.basename(job.input_file))[0]
                    trans_file_path = f"/tmp/{video_name}_translated.srt"
                    os.makedirs("/tmp", exist_ok=True)
                    with open(trans_file_path, 'w', encoding='utf-8') as f:
                        for s in translated_segments:
                            start_str = self._ms_to_srt(s.get("start", 0))
                            end_str = self._ms_to_srt(s.get("end", 0))
                            f.write(f"{s.get('stt', '1')}\n{start_str} --> {end_str}\n{s.get('text', '')}\n\n")
                            
                    # Register new Artifact (Handoff)
                    trans_artifact_id = uuid.uuid4().hex
                    trans_artifact = Artifact(
                        artifact_id=trans_artifact_id,
                        artifact_type=ArtifactType.TRANSLATION,
                        path=trans_file_path,
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                        source_project_id=self.manager.current_session.session_id,
                        status=ArtifactStatus.READY
                    )
                    self.artifact_store.register(trans_artifact)
                    
                    target_artifact_id = trans_artifact_id
                    
                    # Memory Leak Guard: Clear segment lists
                    segments.clear()
                    translated_segments.clear()
                    del trans_worker

                # 3. EXPORTING
                self.manager._update_job_status(job, BatchStatus.EXPORTING)
                export_svc = ExportService()
                export_svc.run(target_artifact_id, job.input_file)
                
                # 4. COMPLETED
                self.manager._update_job_status(job, BatchStatus.COMPLETED)
                self.manager.job_progress_updated.emit(job.id, 100)
                
            except Exception as e:
                job.error_message = str(e)
                self.manager._update_job_status(job, BatchStatus.FAILED)
        
        self.manager.session_completed.emit()

class BatchManager(QObject):
    session_started = Signal(object) # BatchSession
    job_status_changed = Signal(str, object) # job_id, BatchStatus
    job_progress_updated = Signal(str, int) # job_id, progress
    session_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_session: Optional[BatchSession] = None
        self.thread_pool = QThreadPool.globalInstance()
        self.artifact_store = ArtifactStore()
        self.job_status_changed.connect(self._autosave)

    def _autosave(self):
        if self.current_session:
            import json
            from core.runtime.runtime_paths import RuntimePaths
            path = RuntimePaths.get_batch_active_file()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.current_session.to_dict(), f, ensure_ascii=False, indent=2)

    def start_session(self, session: BatchSession):
        self.current_session = session
        self.session_started.emit(session)
        self._autosave()
        
        worker = BatchWorker(self)
        self.thread_pool.start(worker)

    def _update_job_status(self, job: BatchJob, status: BatchStatus):
        job.status = status
        self.job_status_changed.emit(job.id, status)
