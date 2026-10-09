from core.subtitle_generation.generation_error import GenerationError, GenerationErrorCode
import os
import re
import uuid
import copy
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Slot

from core.subtitle_generation.boundary_reconciler import BoundaryReconciler
from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.generation_checkpoint_manager import (
    SubtitleGenerationCheckpointManager,
)
from core.subtitle_generation.generation_planner import SubtitleGenerationPlanner
from core.subtitle_generation.generation_validator import SubtitleGenerationValidator
from core.subtitle_generation.subtitle_artifact_service import SubtitleArtifactService
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_checkpoint import (
    SubtitleGenerationCheckpoint,
)
from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from core.subtitle_generation.generation_range import (
    GenerationRange,
    GenerationRangeStatus,
    validate_generation_range,
)
from core.subtitle_generation.generation_timing_reconciler import (
    ReconciliationStatus,
    reconcile_generated_timing,
)
from core.subtitle_generation.subtitle_generation_result import (
    SubtitleGenerationResult,
    WhisperSegmentResult,
)
from core.transcription.prompt_context_builder import (
    CompiledPromptContext,
    PromptContextBuilder,
)
from core.transcription.token_counter import ApproximateTokenCounter
from core.project.transcription_context import TranscriptionContext
from workers.subtitle_generation_worker import SubtitleGenerationWorker


class SubtitleGenerationService(QObject):
    """Main-thread orchestrator for one-at-a-time, resumable ASR batches."""

    def __init__(self, whisper_service: FasterWhisperService, project_service):
        super().__init__()
        self.whisper_service = whisper_service
        self.project_service = project_service
        self.prompt_context_builder = PromptContextBuilder(ApproximateTokenCounter())
        self.checkpoint_manager = SubtitleGenerationCheckpointManager(project_service)
        self.artifact_service = SubtitleArtifactService(project_service)
        self.current_worker: Optional[SubtitleGenerationWorker] = None
        self.current_request: Optional[SubtitleGenerationRequest] = None
        self.current_batches: List[SubtitleGenerationBatch] = []
        self.current_checkpoint: Optional[SubtitleGenerationCheckpoint] = None
        self.current_timing_ranges = []
        self.all_checkpoints = []
        self._is_cancelled = False
        self._pending_dispatch = False
        self._pending_finish = False
        self._pending_error: Optional[str] = None
        self._terminal_notified = False
        self._is_range_generation = False
        self._range_committed = False
        self._range_artifact_id = None
        self._range_state_artifact_id = None
        self._range_artifact_revision = 0
        self._range_artifact_hash = ""
        self._range_duration_ms = 0
        self._range_editor_segments = None
        self.last_range_reconciliation = None
        self.range_segments_provider = None

        # Optional UI callbacks kept decoupled from the service.
        self.on_progress: Optional[Callable[[int, str], None]] = None
        self.on_batch_complete: Optional[Callable[[SubtitleGenerationBatch, list], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_finish: Optional[Callable[[], None]] = None


    @property
    def checkpoint_history(self):
        project = self.project_service.current_project
        source_id = getattr(project.state, "active_subtitle_source_id", "default") if project else "default"
        return [cp for cp in getattr(self, "all_checkpoints", []) if getattr(cp, "checkpoint_type", "") != "INITIAL" and getattr(cp, "source_id", "default") == source_id]

    @property
    def initial_state(self):
        project = self.project_service.current_project
        source_id = getattr(project.state, "active_subtitle_source_id", "default") if project else "default"
        for cp in getattr(self, "all_checkpoints", []):
            if getattr(cp, "checkpoint_type", "") == "INITIAL" and getattr(cp, "source_id", "default") == source_id:
                return cp
        return None

    def _clear_current_source_history(self):
        project = self.project_service.current_project
        if not project: return
        source_id = getattr(project.state, "active_subtitle_source_id", "default")
        self.all_checkpoints = [cp for cp in getattr(self, "all_checkpoints", []) if getattr(cp, "source_id", "default") != source_id]

    def compile_prompt_context(
        self, context: TranscriptionContext
    ) -> CompiledPromptContext:
        return self.prompt_context_builder.build(context)

    @property
    def is_running(self) -> bool:
        """Whether the worker thread is still alive, including cancellation."""
        return bool(self.current_worker and self.current_worker.isRunning())

    def start_generation(
        self, request: SubtitleGenerationRequest, video_duration_ms: int,
        *, existing_segments=None, conflict_strategy=None
    ) -> None:
        from core.subtitle_generation.range_validation import RangeValidator, ConflictStrategy
        self._ensure_idle()
        self._range_conflict_strategy = conflict_strategy or ConflictStrategy.REPLACE_OVERLAP

        project = self._require_project()
        self._validate_request_source(request, project)
        if video_duration_ms <= 0:
            raise ValueError("Video duration must be positive.")

        if request.range_start_ms is not None and request.range_end_ms is not None:
            # Phase 2: Range Validation
            result = RangeValidator.preview_range(
                request.range_start_ms, request.range_end_ms, video_duration_ms, existing_segments or [], False
            )
            if not result.is_valid:
                raise GenerationError(GenerationErrorCode.VALIDATION_FAILED, f"{result.message}")
            if result.overlapping_count > 0 and self._range_conflict_strategy == ConflictStrategy.CANCEL:
                raise GenerationError(GenerationErrorCode.RANGE_CONFLICT, f"Range overlaps with {result.overlapping_count} existing subtitles.")
                
        if existing_segments is not None:
            self.create_history_checkpoint(existing_segments, is_initial=True)
        else:
            # We can't snapshot without segments. Maybe load from artifact?
            pass

        if request.range_start_ms is not None or request.range_end_ms is not None:
            self._start_range_generation(
                request, video_duration_ms, existing_segments
            )
            return

        self._is_range_generation = False

        artifact = self.artifact_service.get_or_create_artifact()
        if artifact is None:
            raise RuntimeError("Unable to create subtitle artifact.")

        segment_ranges = None
        timing_segment_cursor = 0
        timing_segment_count = 0
        if request.batch_mode == "segments":
            all_timing_ranges = self._load_timing_segment_ranges(project)
            timing_segment_cursor = self._get_timing_segment_cursor(
                project, artifact, len(all_timing_ranges)
            )
            self._ensure_timing_rows(artifact, all_timing_ranges)
            segment_ranges = all_timing_ranges[
                timing_segment_cursor : timing_segment_cursor
                + request.batch_size_value
            ]
            if not segment_ranges:
                raise ValueError("Tất cả Timing segments đã được điền phụ đề.")
            timing_segment_count = len(segment_ranges)
        self.current_timing_ranges = list(segment_ranges or [])

        self._clear_current_source_history()
        self._is_cancelled = False
        self._pending_dispatch = False
        self._pending_finish = False
        self._pending_error = None
        self._terminal_notified = False
        self.current_request = request
        self.current_batches = SubtitleGenerationPlanner.create_plan(
            video_duration_ms,
            request.batch_mode,
            request.batch_size_value,
            request.overlap_ms,
            segment_ranges=segment_ranges,
        )
        artifact_hash = self.artifact_service.content_hash(artifact.path)
        self.current_checkpoint = SubtitleGenerationCheckpoint(
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint,
            request_id=request.request_id,
            subtitle_artifact_id=artifact.artifact_id,
            artifact_revision=artifact.revision,
            completed_batches=[],
            request_data=asdict(request),
            batches_data=[asdict(batch) for batch in self.current_batches],
            active_batch=None,
            next_start_ms=0,
            detected_language=None,
            updated_at=self._now(),
            artifact_content_hash=artifact_hash,
            timing_segment_cursor=timing_segment_cursor,
            timing_segment_count=timing_segment_count,
        )
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
        self.whisper_service.load_model(request.model_size, request.compute_type)
        self._dispatch_next_batch()

    def _start_range_generation(self, request, duration_ms, existing_segments):
        project = self._require_project()
        start_ms, end_ms = request.range_start_ms, request.range_end_ms
        artifact_id = getattr(project.state, "subtitle_artifact_id", None)
        artifact = self.project_service.artifact_store.get(artifact_id) if artifact_id else None
        artifact_segments = (
            self.artifact_service.load_data(artifact.path).get("segments", [])
            if artifact and os.path.exists(artifact.path)
            else []
        )
        validation = validate_generation_range(
            start_ms, end_ms, duration_ms,
            self._resolve_range_coverage(artifact_segments, existing_segments),
        )
        if validation.status != GenerationRangeStatus.VALID:
            raise ValueError(validation.status.value)

        self._is_range_generation = True
        self._range_committed = False
        self.last_range_reconciliation = None
        self._range_artifact_id = artifact.artifact_id if artifact else None
        self._range_state_artifact_id = artifact_id
        self._range_artifact_revision = artifact.revision if artifact else 0
        self._range_artifact_hash = (
            self.artifact_service.content_hash(artifact.path)
            if artifact and os.path.exists(artifact.path)
            else ""
        )
        self._range_editor_segments = existing_segments
        self._range_duration_ms = duration_ms
        self.current_timing_ranges = []
        self.all_checkpoints = []
        self._is_cancelled = False
        self._pending_dispatch = False
        self._pending_finish = False
        self._pending_error = None
        self._terminal_notified = False
        self.current_request = request
        batch = SubtitleGenerationBatch(
            batch_id=str(uuid.uuid4()),
            start_ms=start_ms,
            end_ms=end_ms,
            status="PENDING",
            revision=0,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.current_batches = [batch]
        self.current_checkpoint = SubtitleGenerationCheckpoint(
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint,
            request_id=request.request_id,
            subtitle_artifact_id=artifact.artifact_id if artifact else (artifact_id or ""),
            artifact_revision=artifact.revision if artifact else 0,
            completed_batches=[],
            request_data=asdict(request),
            batches_data=[asdict(batch)],
            active_batch=None,
            next_start_ms=start_ms,
            detected_language=None,
            updated_at=self._now(),
            artifact_content_hash=self._range_artifact_hash,
        )
        self.whisper_service.load_model(request.model_size, request.compute_type)
        self._dispatch_next_batch()

    def resume_generation(self) -> None:
        self._ensure_idle()
        self._is_range_generation = False
        project = self._require_project()
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if checkpoint is None:
            raise ValueError("No subtitle-generation checkpoint found.")
        self._validate_checkpoint(checkpoint, project)

        artifact = self.artifact_service.get_or_create_artifact()
        if artifact is None or artifact.artifact_id != checkpoint.subtitle_artifact_id:
            raise ValueError("Subtitle artifact does not match checkpoint.")
        if artifact.revision != checkpoint.artifact_revision:
            raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "subtitle artifact changed externally.")
        if checkpoint.artifact_content_hash:
            current_hash = self.artifact_service.content_hash(artifact.path)
            if current_hash != checkpoint.artifact_content_hash:
                raise RuntimeError(
                    "STALE_SUBTITLE_FILE: subtitle artifact was edited externally."
                )

        self._clear_current_source_history()
        self._is_cancelled = False
        self._pending_dispatch = False
        self._pending_finish = False
        self._pending_error = None
        self._terminal_notified = False
        self.current_request = SubtitleGenerationRequest(**checkpoint.request_data)
        self.current_timing_ranges = []
        if self.current_request.batch_mode == "segments":
            all_timing_ranges = self._load_timing_segment_ranges(project)
            count = (
                checkpoint.timing_segment_count
                or self.current_request.batch_size_value
            )
            self.current_timing_ranges = all_timing_ranges[
                checkpoint.timing_segment_cursor : checkpoint.timing_segment_cursor
                + count
            ]
        self.current_batches = [
            SubtitleGenerationBatch(**batch_data)
            for batch_data in checkpoint.batches_data
        ]
        completed = set(checkpoint.completed_batches)
        for batch in self.current_batches:
            if batch.batch_id in completed:
                batch.status = "COMPLETED"
            else:
                # The checkpoint list is authoritative. A crash can leave the
                # serialized batch status ahead of the committed-batch list.
                batch.status = "PENDING"
        self.current_checkpoint = checkpoint
        self.current_checkpoint.status = "RUNNING"
        self.current_checkpoint.active_batch = None
        self.current_checkpoint.updated_at = self._now()
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
        self.whisper_service.load_model(
            self.current_request.model_size, self.current_request.compute_type
        )
        self._dispatch_next_batch()

    def cancel_generation(self) -> None:
        self._is_cancelled = True
        self._pending_dispatch = False
        worker = self.current_worker
        if worker and worker.isRunning():
            worker.cancel()
        if self.current_checkpoint:
            self.current_checkpoint.status = "CANCELLED"
            self.current_checkpoint.active_batch = None
            self.current_checkpoint.updated_at = self._now()
            self._save_checkpoint()
        # Do not unload the model or notify the UI while inference is still
        # inside QThread.run(). Resume becomes available only after finished.
        self._pending_finish = True
        self._complete_terminal_if_idle()

    def _dispatch_next_batch(self) -> None:
        if self._is_cancelled or not self.current_checkpoint:
            return
        batch = next(
            (candidate for candidate in self.current_batches if candidate.status != "COMPLETED"),
            None,
        )
        if batch is None:
            self.current_checkpoint.status = "COMPLETED"
            self.current_checkpoint.active_batch = None
            self.current_checkpoint.updated_at = self._now()
            self._save_checkpoint()
            completion_message = "Subtitle generation completed."
            report = self.last_range_reconciliation
            if (
                self._is_range_generation
                and report
                and report.changed_segment_count
            ):
                completion_message = "Đã tạo phụ đề và tự điều chỉnh thời gian."
            self._notify_progress(100, completion_message)
            self._pending_finish = True
            self._complete_terminal_if_idle()
            return

        self.current_checkpoint.active_batch = asdict(batch)
        self.current_checkpoint.updated_at = self._now()
        self._save_checkpoint()
        completed_count = len(self.current_checkpoint.completed_batches)
        total = len(self.current_batches)
        self._notify_progress(
            int(completed_count * 100 / total) if total else 0,
            f"Processing batch {completed_count + 1}/{total}: "
            f"{batch.start_ms / 1000:.1f}s–{batch.end_ms / 1000:.1f}s",
        )

        self.current_worker = SubtitleGenerationWorker(
            self.current_request, batch, self.whisper_service
        )
        worker = self.current_worker
        self.current_worker.batch_success_signal.connect(self._commit_batch)
        self.current_worker.error_signal.connect(self._handle_worker_error)
        # The real QThread always has `finished`; the guard keeps the service
        # usable with lightweight test doubles as well.
        if hasattr(worker, "finished"):
            # Bound QObject slots give Qt a receiver context, so this cleanup
            # is queued back to the service's Main Thread instead of running
            # inside the worker thread.
            worker.finished.connect(self._on_worker_finished_signal)
        worker.start()

    @Slot(object, object)



    def _ensure_history_loaded(self):
        project = self.project_service.current_project
        if not project:
            return
        if getattr(self, '_history_project_id', None) != project.project_id:
            self.load_history()
            self._history_project_id = project.project_id

    def _get_history_path(self) -> str:
        project = self.project_service.current_project
        project_dir = getattr(self.project_service, "project_dir", None) or getattr(
            project, "project_dir", None
        )
        if not project or not project_dir:
            return None
        import os
        checkpoint_dir = os.path.join(
            project_dir, "artifacts", "subtitle_generation"
        )
        os.makedirs(checkpoint_dir, exist_ok=True)
        return os.path.join(checkpoint_dir, "history.json")

    def _save_history(self):
        path = self._get_history_path()
        if not path:
            return
            
        import json
        import os
        data = {
            "all_checkpoints": [cp.__dict__ for cp in getattr(self, "all_checkpoints", [])],
            "initial_state": self.initial_state.__dict__ if self.initial_state else None,
            "history": [cp.__dict__ for cp in self.checkpoint_history]
        }
        
        temp_path = f"{path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def load_history(self):
        path = self._get_history_path()
        if not path or not __import__("os").path.exists(path):
            return
            
        import json
        from core.subtitle_generation.generation_checkpoint import GenerationCheckpoint
        
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                
            def dict_to_cp(d):
                if not d: return None
                cp = GenerationCheckpoint(
                    checkpoint_id=d.get("checkpoint_id"),
                    project_id=d.get("project_id"),
                    source_fingerprint=d.get("source_fingerprint"),
                    generated_count=d.get("generated_count"),
                    segments_snapshot=d.get("segments_snapshot", []),
                    generation_range=d.get("generation_range"),
                    generation_request_id=d.get("generation_request_id"),
                    checkpoint_type=d.get("checkpoint_type", "BATCH"),
                    model_settings=d.get("model_settings", {}),
                source_id=d.get("source_id", "default")
            )
                cp.created_at = d.get("created_at", __import__("time").time())
                return cp
                
            if "all_checkpoints" in data:
                self.all_checkpoints = [dict_to_cp(d) for d in data.get("all_checkpoints", [])]
            else:
                self.all_checkpoints = []
                initial = dict_to_cp(data.get("initial_state"))
                if initial: self.all_checkpoints.append(initial)
                self.all_checkpoints.extend([dict_to_cp(d) for d in data.get("history", [])])
        except Exception:
            pass

    def create_history_checkpoint(self, segments, is_initial=False, is_range=False):
        """Creates a snapshot of the generation state and appends to history."""
        self._ensure_history_loaded()
        from core.subtitle_generation.generation_checkpoint import GenerationCheckpoint
        project = self.project_service.current_project
        if not project:
            return
            
        if is_initial:
            c_type = "INITIAL"
        else:
            c_type = "RANGE_GENERATION_BATCH" if is_range else "FULL_GENERATION_BATCH"
            
        cp = GenerationCheckpoint(
            checkpoint_id=str(__import__("uuid").uuid4()),
            project_id=project.project_id,
            source_fingerprint=project.source.fingerprint if hasattr(project, "source") else "",
            generated_count=len(segments),
            segments_snapshot=segments,
            checkpoint_type=c_type,
            generation_request_id=self.current_request.request_id if self.current_request else None,
            source_id=getattr(project.state, "active_subtitle_source_id", "default")
        )
        
        if is_initial:
            if not self.initial_state:
                self.all_checkpoints.append(cp)
                self._save_history()
        else:
            self.all_checkpoints.append(cp)
            self._save_history()
            
    def get_rollback_checkpoint(self, target_count=None, checkpoint_id=None):
        """
        Resolves the target rollback checkpoint.
        """
        self._ensure_history_loaded()
        if checkpoint_id:
            if self.initial_state and self.initial_state.checkpoint_id == checkpoint_id:
                return self.initial_state
            for cp in self.checkpoint_history:
                if cp.checkpoint_id == checkpoint_id:
                    return cp
            return None
            
        if target_count == 0:
            return self.initial_state
            
        if target_count is not None:
            # Exact match only
            for cp in self.checkpoint_history:
                if cp.generated_count == target_count:
                    return cp
                    
        return None


    def execute_rollback(self, target_count, data_provider, undo_manager, checkpoint_id=None):
        """
        Executes a rollback to a specific target_count by pushing a RestoreGenerationCommand
        to the provided undo_manager.
        """
        cp = self.get_rollback_checkpoint(target_count, checkpoint_id=checkpoint_id)
        if cp is None:
            raise ValueError(f"No checkpoint found near target count: {target_count}")
            
        from core.subtitle_editing.commands.restore_generation_command import RestoreGenerationCommand
        
        # Check for manual edits (for UI reporting later)
        has_manual = cp.has_manual_edits_compared_to(data_provider)
        
        command = RestoreGenerationCommand(
            before_segments=data_provider,
            after_segments=cp.segments_snapshot,
            data_provider=data_provider
        )
        undo_manager.push(command)
        return has_manual

    def _commit_batch(
        self, batch: SubtitleGenerationBatch, result: SubtitleGenerationResult
    ) -> None:
        if self._is_cancelled or not self.current_checkpoint:
            return
        if self._is_range_generation:
            self._commit_range_batch(batch, result)
            return
        try:
            project = self._require_project()
            self._validate_request_source(self.current_request, project)
            artifact = self.artifact_service.get_or_create_artifact()
            if artifact is None:
                raise RuntimeError("Subtitle artifact is unavailable.")
            if artifact.artifact_id != self.current_checkpoint.subtitle_artifact_id:
                raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact identity changed.")
            if artifact.revision != self.current_checkpoint.artifact_revision:
                raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact revision changed.")
            self._assert_live_artifact_hash(artifact)

            valid = SubtitleGenerationValidator.validate(
                result.segments, batch.start_ms, batch.end_ms
            )
            if self.current_request.batch_mode == "segments":
                valid = self._align_text_to_timing_ranges(
                    valid, self.current_timing_ranges
                )
            data = self.artifact_service.load_data(artifact.path)
            existing = data.get("segments", [])
            if self.current_request.batch_mode == "segments":
                reconciled = self._fill_timing_rows(existing, valid)
            else:
                reconciled = BoundaryReconciler.reconcile(existing, valid)
                existing.extend(
                    {
                        "id": str(uuid.uuid4()),
                        "start_ms": segment.start_ms,
                        "end_ms": segment.end_ms,
                        "text": segment.text,
                        "words": segment.words,
                        "status": "generated",
                    }
                    for segment in reconciled
                )
            existing.sort(key=lambda segment: (segment["start_ms"], segment["end_ms"]))
            data["segments"] = existing
            self.artifact_service._save_atomic(artifact.path, data)

            artifact.revision += 1
            artifact.updated_at = self._now()
            batch.status = "COMPLETED"
            batch.updated_at = self._now()
            self.current_checkpoint.completed_batches.append(batch.batch_id)
            self.create_history_checkpoint(existing, is_range=self._is_range_generation)
            self.current_checkpoint.artifact_revision = artifact.revision
            self.current_checkpoint.artifact_content_hash = (
                self.artifact_service.content_hash(artifact.path)
            )
            self.current_checkpoint.active_batch = None
            self.current_checkpoint.next_start_ms = batch.end_ms
            if self.current_request.batch_mode == "segments":
                self.current_checkpoint.timing_segment_cursor += (
                    self.current_checkpoint.timing_segment_count
                )
            self.current_checkpoint.batches_data = [
                asdict(candidate) for candidate in self.current_batches
            ]
            self.current_checkpoint.updated_at = self._now()
            mark_dirty = getattr(self.project_service, "mark_dirty", None)
            if mark_dirty:
                mark_dirty()
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            if self.on_batch_complete:
                self.on_batch_complete(batch, reconciled)
            # The success signal can be delivered just before QThread.run()
            # returns. Wait for finished so only one worker is alive at a time.
            self._pending_dispatch = True
            self._dispatch_next_batch_if_idle()
        except Exception as exc:
            batch.status = "STALE" if "STALE_SUBTITLE" in str(exc) else "FAILED"
            self._fail(str(exc))

    @Slot(str)
    def _handle_worker_error(self, message: str) -> None:
        if not self._is_cancelled:
            self._fail(message)

    def _fail(self, message: str) -> None:
        if self._terminal_notified or self._pending_error:
            return
        if self.current_checkpoint:
            self.current_checkpoint.status = "FAILED"
            self.current_checkpoint.updated_at = self._now()
            self._save_checkpoint()
        self._pending_dispatch = False
        self._pending_error = message
        self._complete_terminal_if_idle()

    def _dispatch_next_batch_if_idle(self) -> None:
        if self.is_running:
            return
        if self._pending_dispatch:
            self._pending_dispatch = False
            self._dispatch_next_batch()

    @Slot()
    def _on_worker_finished_signal(self) -> None:
        worker = self.sender()
        if worker is not None:
            self._on_worker_finished(worker)

    def _on_worker_finished(self, worker) -> None:
        if worker is not self.current_worker:
            return
        self.current_worker = None
        self._dispatch_next_batch_if_idle()
        self._complete_terminal_if_idle()

    def _complete_terminal_if_idle(self) -> None:
        if self.is_running or self._terminal_notified:
            return
        if not self._pending_finish and not self._pending_error:
            return

        self._terminal_notified = True
        pending_error = self._pending_error
        self._pending_error = None
        self._pending_finish = False
        self.whisper_service.unload_model()

        if pending_error:
            if self.on_error:
                self.on_error(pending_error)
        elif self.on_finish:
            self.on_finish()

    def _ensure_idle(self) -> None:
        if self.current_worker and self.current_worker.isRunning():
            raise RuntimeError("Subtitle generation is already running.")

    def _save_checkpoint(self):
        if not self._is_range_generation:
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)

    def _commit_range_batch(self, batch, result):
        if self._is_cancelled or not self.current_checkpoint:
            return
        try:
            if not result.segments:
                raise RuntimeError("No subtitle segments were generated for this range.")
            project = self._require_project()
            self._validate_request_source(self.current_request, project)
            state_artifact_id = getattr(project.state, "subtitle_artifact_id", None)
            artifact = (
                self.project_service.artifact_store.get(state_artifact_id)
                if state_artifact_id else None
            )
            artifact_data = (
                self.artifact_service.load_data(artifact.path)
                if artifact and os.path.exists(artifact.path)
                else {"version": 1, "segments": []}
            )
            artifact_rows = artifact_data.get("segments", [])
            current_subtitles = self._resolve_range_coverage(
                artifact_rows, self._range_editor_segments
            )
            
            # PHASE 2: Apply Conflict Strategy before reconciliation
            from core.subtitle_generation.range_validation import ConflictStrategy
            if getattr(self, "_range_conflict_strategy", ConflictStrategy.REPLACE_OVERLAP) == ConflictStrategy.REPLACE_OVERLAP:
                def is_overlapping(seg, r_start, r_end):
                    try:
                        s_start = int(seg.get("start_ms", 0)) if "start_ms" in seg else int(seg.start_ms)
                        s_end = int(seg.get("end_ms", 0)) if "end_ms" in seg else int(seg.end_ms)
                        return s_start < r_end and s_end > r_start
                    except (AttributeError, ValueError, TypeError):
                        pass
                    # Try string parser
                    from core.export.subtitle_parser import time_str_to_ms
                    try:
                        s_start = time_str_to_ms(seg.get("start", ""))
                        s_end = time_str_to_ms(seg.get("end", ""))
                        return s_start < r_end and s_end > r_start
                    except (AttributeError, ValueError, TypeError):
                        return False
                        
                current_subtitles = [
                    seg for seg in current_subtitles 
                    if not is_overlapping(seg, batch.start_ms, batch.end_ms)
                ]

            reconciled = reconcile_generated_timing(
                GenerationRange(batch.start_ms, batch.end_ms),
                result.segments,
                self._range_duration_ms,
                current_subtitles=current_subtitles,
            )
            self.last_range_reconciliation = reconciled
            if reconciled.status == ReconciliationStatus.STALE_RANGE_CONFLICT:
                raise GenerationError(GenerationErrorCode.STALE_RANGE_CONFLICT, f"{reconciled.reason}")
            if reconciled.status != ReconciliationStatus.SUCCESS:
                raise GenerationError(GenerationErrorCode.RECONCILIATION_UNSAFE, f"{reconciled.reason}")

            if state_artifact_id != self._range_state_artifact_id:
                raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact identity changed during range generation.")
            if (artifact.artifact_id if artifact else None) != self._range_artifact_id:
                raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact identity changed during range generation.")
            if artifact and artifact.revision != self._range_artifact_revision:
                raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact revision changed during range generation.")
            if artifact and self._range_artifact_hash:
                if self.artifact_service.content_hash(artifact.path) != self._range_artifact_hash:
                    raise GenerationError(GenerationErrorCode.STALE_SUBTITLE, "artifact changed during range generation.")

            generated = SubtitleGenerationValidator.validate(
                list(reconciled.segments), batch.start_ms, batch.end_ms
            )
            if len(generated) != len(reconciled.segments):
                raise GenerationError(GenerationErrorCode.RECONCILIATION_UNSAFE, "generated output failed subtitle validation.")
            rows = copy.deepcopy([
                segment.get_raw_dict() if hasattr(segment, "get_raw_dict") else segment
                for segment in current_subtitles
            ])
            rows.extend(
                {
                    "id": str(uuid.uuid4()),
                    "start_ms": int(segment.start_ms),
                    "end_ms": int(segment.end_ms),
                    "text": segment.text,
                    "words": segment.words,
                    "status": "generated",
                }
                for segment in generated
            )
            rows.sort(key=lambda row: (int(row["start_ms"]), int(row["end_ms"])))
            data = dict(artifact_data)
            data["segments"] = rows

            if artifact:
                self.artifact_service._save_atomic(artifact.path, data)
                artifact.revision += 1
                artifact.updated_at = self._now()
                mark_dirty = getattr(self.project_service, "mark_dirty", None)
                if mark_dirty:
                    mark_dirty()
            else:
                artifact = self.artifact_service.create_artifact_with_data(data)
                if artifact is None:
                    raise RuntimeError("Unable to create subtitle artifact.")

            self._range_committed = True
            self.current_checkpoint.status = "COMPLETED"
            self.current_checkpoint.artifact_revision = artifact.revision
            self.current_checkpoint.artifact_content_hash = self.artifact_service.content_hash(artifact.path)
            self.current_checkpoint.completed_batches = [batch.batch_id]
            batch.status = "COMPLETED"
            batch.updated_at = self._now()
            if self.on_batch_complete:
                self.on_batch_complete(batch, generated)
            self._pending_dispatch = True
            self._dispatch_next_batch_if_idle()
        except Exception as exc:
            batch.status = "FAILED"
            self._fail(str(exc))

    def _resolve_range_coverage(self, artifact_rows, supplied_segments):
        """Providers/callers supply complete rows for the validated request context.

        None means unavailable; an empty list is authoritative, not a fallback.
        Call again immediately before insertion to observe edits made during ASR.
        """
        current = (
            self.range_segments_provider()
            if callable(self.range_segments_provider)
            else supplied_segments
        )
        return list(artifact_rows if current is None else current)

    def _require_project(self):
        project = self.project_service.current_project
        if not project:
            raise ValueError("No project is currently open.")
        return project

    def _validate_request_source(self, request, project) -> None:
        if request.project_id != project.project_id:
            raise ValueError("Sai Project ID: request belongs to another project.")
        if request.source_fingerprint != project.source.fingerprint:
            raise ValueError("Source đã thay đổi: fingerprint does not match.")
        source_path = getattr(project.source, "path", None)
        if source_path:
            if os.path.normcase(request.video_path) != os.path.normcase(source_path):
                raise ValueError("Source đã thay đổi: video path does not match.")
            if not os.path.exists(source_path):
                raise FileNotFoundError("Project source video was not found.")

    def _validate_checkpoint(self, checkpoint, project) -> None:
        if checkpoint.project_id != project.project_id:
            raise ValueError("Sai Project ID: checkpoint belongs to another project.")
        if checkpoint.source_fingerprint != project.source.fingerprint:
            raise ValueError("Source đã thay đổi: checkpoint fingerprint does not match.")

    def _load_timing_segment_ranges(self, project):
        """Read real segment ranges from the project's Timing Artifact."""
        timing_state = getattr(project.state, "timing", None)
        timing_artifact_id = getattr(timing_state, "timing_artifact_id", None)
        artifact = (
            self.project_service.artifact_store.get(timing_artifact_id)
            if timing_artifact_id
            else None
        )
        if not artifact or not os.path.exists(artifact.path):
            raise ValueError(
                "Segment-based batching requires a completed Timing Artifact."
            )

        ranges = []
        with open(artifact.path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        for line in lines:
            if "-->" not in line:
                continue
            start_text, end_text = (part.strip() for part in line.split("-->", 1))
            try:
                start_ms = self._parse_srt_time_ms(start_text)
                end_ms = self._parse_srt_time_ms(end_text)
            except ValueError:
                continue
            if end_ms > start_ms:
                ranges.append((start_ms, end_ms))

        if not ranges:
            raise ValueError("Timing Artifact does not contain valid subtitle ranges.")
        return ranges

    def _get_timing_segment_cursor(self, project, artifact, total_ranges: int) -> int:
        """Restore the next segment index only for the same safe ASR artifact."""
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if not checkpoint:
            return 0
        if (
            checkpoint.project_id != project.project_id
            or checkpoint.source_fingerprint != project.source.fingerprint
            or checkpoint.subtitle_artifact_id != artifact.artifact_id
            or checkpoint.request_data.get("batch_mode") != "segments"
        ):
            return 0
        return max(0, min(int(checkpoint.timing_segment_cursor), total_ranges))

    def _assert_live_artifact_hash(self, artifact) -> None:
        """Reject a file edit made after the batch checkpoint was written."""
        expected_hash = self.current_checkpoint.artifact_content_hash
        if not expected_hash or not os.path.exists(artifact.path):
            return
        current_hash = self.artifact_service.content_hash(artifact.path)
        if current_hash != expected_hash:
            raise RuntimeError(
                "STALE_SUBTITLE_FILE: subtitle artifact was edited externally "
                "during inference."
            )

    def _ensure_timing_rows(self, artifact, timing_ranges) -> None:
        """Seed missing subtitle rows from Timing without replacing unrelated data."""
        data = self.artifact_service.load_data(artifact.path)
        existing = data.get("segments", [])
        timing_keys = [(int(start_ms), int(end_ms)) for start_ms, end_ms in timing_ranges]
        timing_key_set = set(timing_keys)
        existing_by_range = {}

        for row in existing:
            key = (int(row.get("start_ms", -1)), int(row.get("end_ms", -1)))
            if key not in timing_key_set or key in existing_by_range:
                return
            existing_by_range[key] = row

        synchronized = []
        for start_ms, end_ms in timing_keys:
            row = existing_by_range.get((start_ms, end_ms))
            if row is None:
                row = {
                    "id": str(uuid.uuid4()),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": "",
                    "words": None,
                    "status": "timing",
                }
            synchronized.append(row)

        if synchronized == existing:
            return

        data["segments"] = synchronized
        self.artifact_service._save_atomic(artifact.path, data)
        artifact.revision += 1
        artifact.updated_at = self._now()
        mark_dirty = getattr(self.project_service, "mark_dirty", None)
        if mark_dirty:
            mark_dirty()

    @staticmethod
    def _fill_timing_rows(existing, segments):
        """Update text in exact Timing slots instead of appending duplicate rows."""
        rows_by_range = {
            (int(row.get("start_ms", -1)), int(row.get("end_ms", -1))): row
            for row in existing
        }
        applied = []
        for segment in segments:
            key = (int(segment.start_ms), int(segment.end_ms))
            row = rows_by_range.get(key)
            if row is None:
                row = {
                    "id": str(uuid.uuid4()),
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                }
                existing.append(row)
                rows_by_range[key] = row
            row.update(
                {
                    "text": segment.text,
                    "words": segment.words,
                    "status": "generated",
                }
            )
            applied.append(segment)
        return applied

    @staticmethod
    def _align_text_to_timing_ranges(segments, timing_ranges):
        """Keep Timing boundaries authoritative while assigning ASR text."""
        text_buckets = [[] for _range in timing_ranges]
        for segment in segments:
            overlaps = [
                max(
                    0,
                    min(segment.end_ms, end_ms)
                    - max(segment.start_ms, start_ms),
                )
                for start_ms, end_ms in timing_ranges
            ]
            if not overlaps or max(overlaps) <= 0:
                continue
            target_index = max(range(len(overlaps)), key=overlaps.__getitem__)
            text = (segment.text or "").strip()
            if text:
                text_buckets[target_index].append(text)

        return [
            WhisperSegmentResult(
                start_ms=start_ms,
                end_ms=end_ms,
                text=" ".join(text_buckets[index]),
                words=None,
            )
            for index, (start_ms, end_ms) in enumerate(timing_ranges)
        ]

    @staticmethod
    def _parse_srt_time_ms(value: str) -> int:
        match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})", value)
        if not match:
            raise ValueError(f"Invalid SRT timestamp: {value}")
        hours, minutes, seconds, milliseconds = match.groups()
        return (
            int(hours) * 3600000
            + int(minutes) * 60000
            + int(seconds) * 1000
            + int(milliseconds.ljust(3, "0"))
        )

    def _notify_progress(self, percent: int, message: str) -> None:
        if self.on_progress:
            self.on_progress(max(0, min(100, percent)), message)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
