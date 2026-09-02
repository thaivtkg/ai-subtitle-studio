import os
import re
import uuid
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
        self._is_cancelled = False
        self._pending_dispatch = False
        self._pending_finish = False
        self._pending_error: Optional[str] = None
        self._terminal_notified = False

        # Optional UI callbacks kept decoupled from the service.
        self.on_progress: Optional[Callable[[int, str], None]] = None
        self.on_batch_complete: Optional[Callable[[SubtitleGenerationBatch, list], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_finish: Optional[Callable[[], None]] = None

    def compile_prompt_context(
        self, context: TranscriptionContext
    ) -> CompiledPromptContext:
        return self.prompt_context_builder.build(context)

    @property
    def is_running(self) -> bool:
        """Whether the worker thread is still alive, including cancellation."""
        return bool(self.current_worker and self.current_worker.isRunning())

    def start_generation(
        self, request: SubtitleGenerationRequest, video_duration_ms: int
    ) -> None:
        self._ensure_idle()
        project = self._require_project()
        self._validate_request_source(request, project)
        if video_duration_ms <= 0:
            raise ValueError("Video duration must be positive.")

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

    def resume_generation(self) -> None:
        self._ensure_idle()
        project = self._require_project()
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if checkpoint is None:
            raise ValueError("No subtitle-generation checkpoint found.")
        self._validate_checkpoint(checkpoint, project)

        artifact = self.artifact_service.get_or_create_artifact()
        if artifact is None or artifact.artifact_id != checkpoint.subtitle_artifact_id:
            raise ValueError("Subtitle artifact does not match checkpoint.")
        if artifact.revision != checkpoint.artifact_revision:
            raise RuntimeError("STALE_SUBTITLE: subtitle artifact changed externally.")
        if checkpoint.artifact_content_hash:
            current_hash = self.artifact_service.content_hash(artifact.path)
            if current_hash != checkpoint.artifact_content_hash:
                raise RuntimeError(
                    "STALE_SUBTITLE_FILE: subtitle artifact was edited externally."
                )

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
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
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
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
            self._notify_progress(100, "Subtitle generation completed.")
            self._pending_finish = True
            self._complete_terminal_if_idle()
            return

        self.current_checkpoint.active_batch = asdict(batch)
        self.current_checkpoint.updated_at = self._now()
        self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
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
    def _commit_batch(
        self, batch: SubtitleGenerationBatch, result: SubtitleGenerationResult
    ) -> None:
        if self._is_cancelled or not self.current_checkpoint:
            return
        try:
            project = self._require_project()
            self._validate_request_source(self.current_request, project)
            artifact = self.artifact_service.get_or_create_artifact()
            if artifact is None:
                raise RuntimeError("Subtitle artifact is unavailable.")
            if artifact.artifact_id != self.current_checkpoint.subtitle_artifact_id:
                raise RuntimeError("STALE_SUBTITLE: artifact identity changed.")
            if artifact.revision != self.current_checkpoint.artifact_revision:
                raise RuntimeError("STALE_SUBTITLE: artifact revision changed.")
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
            self.checkpoint_manager.save_checkpoint(self.current_checkpoint)
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
