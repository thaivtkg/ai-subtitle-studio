import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The acceptance suite is also runnable with the lightweight bundled Python,
# which intentionally does not ship Qt. A real PySide6 installation is used
# automatically when available.
try:
    import PySide6  # noqa: F401
except ModuleNotFoundError:
    class _BoundSignal:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args):
            for slot in list(self._slots):
                slot(*args)

        def disconnect(self, slot=None):
            if slot is None:
                self._slots.clear()
            else:
                self._slots.remove(slot)

    class _Signal:
        def __init__(self, *args):
            self.name = None

        def __set_name__(self, owner, name):
            self.name = f"__signal_{name}"

        def __get__(self, instance, owner):
            if instance is None:
                return self
            signal = instance.__dict__.get(self.name)
            if signal is None:
                signal = instance.__dict__[self.name] = _BoundSignal()
            return signal

    class _QObject:
        def __init__(self, *args, **kwargs):
            super().__init__()

    class _QThread(_QObject):
        def start(self):
            self.run()

        def isRunning(self):
            return False

    qt_core = types.ModuleType("PySide6.QtCore")
    qt_core.QObject = _QObject
    qt_core.QThread = _QThread
    qt_core.Qt = types.SimpleNamespace(AlignCenter=0)
    qt_core.Signal = _Signal
    qt_core.Slot = lambda *args, **kwargs: (lambda function: function)
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qt_core
    qt_widgets = types.ModuleType("PySide6.QtWidgets")
    for widget_name in (
        "QCheckBox",
        "QComboBox",
        "QGroupBox",
        "QHBoxLayout",
        "QLabel",
        "QMessageBox",
        "QProgressBar",
        "QPushButton",
        "QSpinBox",
        "QVBoxLayout",
        "QWidget",
    ):
        setattr(qt_widgets, widget_name, type(widget_name, (), {}))
    qt_widgets.QMessageBox.warning = staticmethod(lambda *args, **kwargs: None)
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qt_core
    sys.modules["PySide6.QtWidgets"] = qt_widgets

from core.artifacts.artifact_types import ArtifactType
from core.artifacts.artifact_store import ArtifactStore
from core.services.project_service import ProjectService
from core.timing.timing_batch_service import TimingBatchService
from core.timing.timing_checkpoint import TimingCheckpoint
from core.timing.timing_run_request import TimingRunRequest
from core.subtitle_generation.boundary_reconciler import BoundaryReconciler
from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.generation_planner import SubtitleGenerationPlanner
from core.subtitle_generation.generation_validator import SubtitleGenerationValidator
from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from core.subtitle_generation.subtitle_generation_result import (
    SubtitleGenerationResult,
    WhisperSegmentResult,
)
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_service import (
    SubtitleGenerationService,
)
from ui.subtitle_generation_panel import SubtitleGenerationPanel
from workers.TimingBatchWorker import TimingBatchWorker
from workers.subtitle_generation_worker import SubtitleGenerationWorker


class MockSource:
    fingerprint = "video_hash_123"


class MockState:
    subtitle_artifact_id = "sub_123"


class MockProject:
    def __init__(self, project_dir):
        self.project_id = "proj_123"
        self.project_dir = project_dir
        self.state = MockState()
        self.source = MockSource()


class MockArtifactStore:
    def __init__(self):
        self._store = {}

    def register(self, artifact):
        self._store[artifact.artifact_id] = artifact

    def get(self, artifact_id):
        return self._store.get(artifact_id)


class MockProjectService:
    def __init__(self, project_dir):
        self.current_project = MockProject(project_dir)
        self.artifact_store = MockArtifactStore()


class MockWhisperService(FasterWhisperService):
    def __init__(self):
        super().__init__()
        self.call_count = 0

    def load_model(self, model_size, compute_type):
        self.model = object()

    def unload_model(self):
        self.model = None

    def transcribe_batch(self, request, batch, is_cancelled):
        self.call_count += 1
        segment = WhisperSegmentResult(
            batch.start_ms + 100, batch.start_ms + 2000, f"Text {batch.start_ms}"
        )
        return SubtitleGenerationResult(batch.batch_id, [segment])


class TestSubtitleGenerationIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_service = MockProjectService(self.test_dir)
        self.whisper = MockWhisperService()
        self.service = SubtitleGenerationService(self.whisper, self.project_service)
        self.original_start = SubtitleGenerationWorker.start
        SubtitleGenerationWorker.start = lambda worker: worker.run()
        self.request = SubtitleGenerationRequest(
            request_id="req_1",
            project_id="proj_123",
            source_fingerprint="video_hash_123",
            video_path="dummy.mp4",
            model_size="tiny",
            compute_type="int8",
            language=None,
            use_vad=True,
            min_silence_ms=500,
            word_timestamps=False,
            batch_duration_ms=300000,
            overlap_ms=2000,
        )

    def tearDown(self):
        SubtitleGenerationWorker.start = self.original_start
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dropped_video_must_not_reuse_a_different_open_project(self):
        """A queue selection may reuse a project only for its own source file."""
        first_video = os.path.join(self.test_dir, "first.mp4")
        dropped_video = os.path.join(self.test_dir, "dropped.mp4")
        for path in (first_video, dropped_video):
            with open(path, "wb") as handle:
                handle.write(b"video")

        project_service = ProjectService(ArtifactStore())
        project_service.create_project(
            os.path.join(self.test_dir, "first.ai-subtitle"),
            "first.mp4",
            first_video,
        )

        self.assertTrue(project_service.is_current_project_for_video(first_video))
        self.assertFalse(project_service.is_current_project_for_video(dropped_video))

    def test_empty_timing_result_is_not_marked_completed_or_registered(self):
        """An empty VAD result must not become a fake READY Timing artifact."""
        video_path = os.path.join(self.test_dir, "silent.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        project_service = ProjectService(ArtifactStore())
        project_service.create_project(
            os.path.join(self.test_dir, "silent.ai-subtitle"),
            "silent.mp4",
            video_path,
        )
        timing_service = TimingBatchService(project_service)
        errors = []
        timing_service.error_signal.connect(errors.append)

        timing_service._on_worker_finished([], True)

        self.assertEqual(project_service.current_project.state.timing_status, "EMPTY")
        self.assertIsNone(
            project_service.current_project.state.timing.timing_artifact_id
        )
        self.assertTrue(errors)

    def test_raw_video_sessions_do_not_reuse_hidden_timing_checkpoints(self):
        """Dropping the same raw video again starts a fresh auto project."""
        video_path = os.path.join(self.test_dir, "raw.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        project_service = ProjectService(ArtifactStore())
        project_service.create_auto_project(
            self.test_dir, "raw.mp4", video_path, "session-one"
        )
        first_dir = project_service.project_dir
        project_service.save_timing_checkpoint(
            TimingCheckpoint(
                project_id=project_service.current_project.project_id,
                source_fingerprint=project_service.current_project.source.fingerprint,
                timing_artifact_id="timing-old",
                timing_revision=1,
                batch_size=10,
                next_segment_index=11,
            )
        )

        project_service.create_auto_project(
            self.test_dir, "raw.mp4", video_path, "session-two"
        )

        self.assertNotEqual(project_service.project_dir, first_dir)
        self.assertIsNone(project_service.load_timing_checkpoint())
        self.assertEqual(
            project_service.current_project.state.timing.next_segment_index, 1
        )

    def test_readding_active_raw_video_still_requests_a_fresh_project(self):
        """Fresh Queue import overrides a currently matching hidden project."""
        video_path = os.path.join(self.test_dir, "same.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        project_service = ProjectService(ArtifactStore())
        project_service.create_auto_project(
            self.test_dir, "same.mp4", video_path, "first-session"
        )

        self.assertFalse(
            project_service.requires_project_switch(video_path, fresh_project=False)
        )
        self.assertTrue(
            project_service.requires_project_switch(video_path, fresh_project=True)
        )

    def test_timing_transaction_preserves_subtitle_artifact_identity(self):
        """Saving Timing must not erase the Full Subtitle artifact cursor key."""
        video_path = os.path.join(self.test_dir, "source.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        project_service = ProjectService(ArtifactStore())
        project_service.create_project(
            os.path.join(self.test_dir, "project.ai-subtitle"),
            "source.mp4",
            video_path,
        )
        project_service.current_project.state.subtitle_artifact_id = "subtitle-1"
        timing_service = TimingBatchService(project_service)
        timing_dir = os.path.join(project_service.project_dir, "artifacts", "timing")
        os.makedirs(timing_dir, exist_ok=True)
        timing_path = os.path.join(timing_dir, "timing.srt")
        checkpoint = TimingCheckpoint(
            project_id=project_service.current_project.project_id,
            source_fingerprint=project_service.current_project.source.fingerprint,
            timing_artifact_id="timing-1",
            timing_revision=1,
            batch_size=5,
        )

        timing_service._commit_transaction(timing_path, "", checkpoint)

        with open(
            os.path.join(project_service.project_dir, "state.json"),
            "r",
            encoding="utf-8",
        ) as handle:
            state = json.load(handle)
        self.assertEqual(state["subtitle_artifact_id"], "subtitle-1")

    def test_timing_worker_retries_empty_vad_with_lower_threshold(self):
        """A voiced chunk rejected by default VAD gets one lower-threshold retry."""
        class RetryModel:
            def __init__(self):
                self.thresholds = []

            def transcribe(self, _path, **options):
                self.thresholds.append(options["vad_parameters"]["threshold"])
                info = types.SimpleNamespace(
                    duration=120.0,
                    duration_after_vad=60.0,
                    language="ja",
                    language_probability=0.9,
                )
                if len(self.thresholds) == 1:
                    return [], info
                return [
                    types.SimpleNamespace(
                        start=15.0, end=17.0, text="speech", words=None
                    )
                ], info

        worker = TimingBatchWorker(
            TimingRunRequest("video.mp4", 0, 10, min_silence_ms=500)
        )
        logs = []
        worker.log_signal.connect(logs.append)
        model = RetryModel()

        segments, _info = worker._transcribe_with_vad_retry(model, "chunk.wav")

        self.assertEqual(model.thresholds, [0.5, 0.25])
        self.assertEqual(len(segments), 1)
        self.assertTrue(any("retry" in message.casefold() for message in logs))

    def test_error_status_label_wraps_without_expanding_the_drawer(self):
        """Long generation errors wrap instead of changing dock width."""
        class Label:
            def __init__(self):
                self.word_wrap = False

            def setWordWrap(self, enabled):
                self.word_wrap = enabled

        label = Label()

        SubtitleGenerationPanel._configure_status_label(label)

        self.assertTrue(label.word_wrap)

    def test_01_planner_partitions_video_by_time(self):
        batches = SubtitleGenerationPlanner.create_plan(1020000, 300000, 2000)
        self.assertEqual(len(batches), 4)
        self.assertEqual((batches[0].start_ms, batches[0].end_ms), (0, 302000))
        self.assertEqual((batches[1].start_ms, batches[1].end_ms), (300000, 602000))
        self.assertEqual((batches[-1].start_ms, batches[-1].end_ms), (900000, 1020000))

    def test_02_full_generation_commits_subtitle_artifact(self):
        self.service.start_generation(self.request, 360000)
        self.assertEqual(self.whisper.call_count, 2)
        artifact = self.project_service.artifact_store.get("sub_123")
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.artifact_type, ArtifactType.SUBTITLE)
        self.assertEqual(artifact.revision, 2)
        self.assertEqual(len(self.service.artifact_service.load_data(artifact.path)["segments"]), 2)

    def test_03_atomic_artifact_and_checkpoint_write(self):
        self.service.start_generation(self.request, 300000)
        artifact = self.project_service.artifact_store.get("sub_123")
        checkpoint = self.service.checkpoint_manager._get_checkpoint_path()
        self.assertTrue(os.path.exists(artifact.path))
        self.assertTrue(os.path.exists(checkpoint))
        self.assertFalse(os.path.exists(artifact.path + ".tmp"))
        self.assertFalse(os.path.exists(checkpoint + ".tmp"))

    def test_04_cancel_does_not_commit_partial_batch(self):
        class CancelWhisper(MockWhisperService):
            def transcribe_batch(self, request, batch, is_cancelled):
                return SubtitleGenerationResult(batch.batch_id, [], "Cancelled")

        self.service.whisper_service = CancelWhisper()
        self.service.start_generation(self.request, 600000)
        self.service.cancel_generation()
        checkpoint = self.service.checkpoint_manager.load_checkpoint()
        self.assertEqual(checkpoint.status, "CANCELLED")
        self.assertEqual(checkpoint.completed_batches, [])

    def test_05_resume_skips_completed_batch(self):
        self.service.start_generation(self.request, 360000)
        checkpoint = self.service.checkpoint_manager.load_checkpoint()
        checkpoint.completed_batches.pop()
        self.service.checkpoint_manager.save_checkpoint(checkpoint)
        self.whisper.call_count = 0
        self.service.resume_generation()
        self.assertEqual(self.whisper.call_count, 1)

    def test_06_resume_retries_active_batch(self):
        self.service.start_generation(self.request, 300000)
        checkpoint = self.service.checkpoint_manager.load_checkpoint()
        checkpoint.active_batch = checkpoint.batches_data[0]
        checkpoint.completed_batches = []
        self.service.checkpoint_manager.save_checkpoint(checkpoint)
        self.whisper.call_count = 0
        self.service.resume_generation()
        self.assertEqual(self.whisper.call_count, 1)

    def test_07_wrong_project_rejects_resume(self):
        self.service.start_generation(self.request, 300000)
        self.project_service.current_project.project_id = "HACKER_PROJ"
        with self.assertRaisesRegex(ValueError, "Sai Project ID"):
            self.service.resume_generation()

    def test_08_source_fingerprint_mismatch_rejects_resume(self):
        self.service.start_generation(self.request, 300000)
        self.project_service.current_project.source.fingerprint = "NEW_VIDEO_HASH"
        with self.assertRaisesRegex(ValueError, "Source"):
            self.service.resume_generation()

    def test_09_subtitle_revision_stale_guard_rejects_commit(self):
        self.service.start_generation(self.request, 300000)
        self.project_service.artifact_store.get("sub_123").revision = 99
        with self.assertRaisesRegex(RuntimeError, "STALE_SUBTITLE"):
            self.service.resume_generation()

    def test_10_boundary_overlap_does_not_duplicate_subtitles(self):
        existing = [{"start_ms": 298000, "end_ms": 300500, "text": "Today is bright."}]
        new = [
            WhisperSegmentResult(298500, 301000, " Today is bright "),
            WhisperSegmentResult(302000, 305000, "We go outside."),
        ]
        reconciled = BoundaryReconciler.reconcile(existing, new)
        self.assertEqual([segment.text for segment in reconciled], ["We go outside."])

    def test_11_validator_rejects_known_whisper_hallucinations(self):
        segments = [
            WhisperSegmentResult(0, 1000, "Transcription by CastingWords"),
            WhisperSegmentResult(1000, 2000, "Nội dung hợp lệ."),
            WhisperSegmentResult(2000, 3000, "Subtitles by Amara.org"),
        ]
        valid = SubtitleGenerationValidator.validate(segments, 0, 3000)
        self.assertEqual([segment.text for segment in valid], ["Nội dung hợp lệ."])

    def test_segment_planner_uses_timing_artifact_boundaries(self):
        timing_ranges = [
            (index * 5000, (index + 1) * 5000) for index in range(20)
        ]
        batches = SubtitleGenerationPlanner.create_plan(
            100000,
            "segments",
            10,
            2000,
            timing_segments=[
                {"start_ms": start_ms, "end_ms": end_ms}
                for start_ms, end_ms in timing_ranges
            ],
        )
        self.assertEqual(len(batches), 2)
        self.assertEqual((batches[0].start_ms, batches[0].end_ms), (0, 52000))
        self.assertEqual((batches[1].start_ms, batches[1].end_ms), (50000, 100000))

    def test_13_request_preserves_segment_batch_configuration(self):
        request = SubtitleGenerationRequest(
            request_id="req_segments",
            project_id="proj_123",
            source_fingerprint="video_hash_123",
            video_path="dummy.mp4",
            model_size="tiny",
            compute_type="int8",
            language=None,
            use_vad=True,
            min_silence_ms=500,
            word_timestamps=False,
            batch_mode="segments",
            batch_size_value=10,
            overlap_ms=2000,
        )
        self.assertEqual(request.batch_mode, "segments")
        self.assertEqual(request.batch_size_value, 10)

    @patch(
        "core.services.model_manager.ModelManager.get_model_path_for_inference",
        return_value="local_fake_path",
    )
    def test_faster_whisper_loads_via_model_manager(self, mock_get_path):
        """ASR must pass the offline-resolved path to Faster-Whisper."""
        whisper_model = MagicMock()
        fake_faster_whisper = types.ModuleType("faster_whisper")
        fake_faster_whisper.WhisperModel = whisper_model
        service = FasterWhisperService(device="cpu")

        with patch.dict(sys.modules, {"faster_whisper": fake_faster_whisper}):
            service.load_model("large-v3-turbo", "int8")

        mock_get_path.assert_called_once_with("large-v3-turbo")
        self.assertEqual(whisper_model.call_args.args[0], "local_fake_path")
        self.assertEqual(whisper_model.call_args.kwargs["device"], "cpu")
        self.assertEqual(whisper_model.call_args.kwargs["compute_type"], "int8")

    def test_commit_rejects_artifact_edited_during_inference(self):
        """A batch commit must fail without overwriting an externally edited artifact."""
        SubtitleGenerationWorker.start = lambda _worker: None
        self.service.start_generation(self.request, 300000)
        artifact = self.project_service.artifact_store.get("sub_123")
        batch = self.service.current_batches[0]
        before_data = self.service.artifact_service.load_data(artifact.path)

        external_data = dict(before_data)
        external_data["external_edit"] = True
        self.service.artifact_service._save_atomic(artifact.path, external_data)

        self.service._commit_batch(
            batch,
            SubtitleGenerationResult(
                batch.batch_id,
                [WhisperSegmentResult(100, 900, "must not be committed")],
            ),
        )

        checkpoint = self.service.checkpoint_manager.load_checkpoint()
        self.assertEqual(checkpoint.status, "FAILED")
        self.assertEqual(batch.status, "STALE")
        self.assertEqual(
            self.service.artifact_service.load_data(artifact.path), external_data
        )

    def test_11_planner_time_vs_segments_mode(self):
        """TC11: Planner hỗ trợ cả Time-based và Segment-based batching."""
        video_10m = 600000

        batches_time = SubtitleGenerationPlanner.create_plan(
            duration_ms=video_10m,
            batch_mode="time",
            size_value=5,
            overlap_ms=2000,
        )
        self.assertGreater(len(batches_time), 0)
        self.assertEqual(batches_time[0].start_ms, 0)
        self.assertEqual(batches_time[0].end_ms, 302000)

        batches_seg = SubtitleGenerationPlanner.create_plan(
            duration_ms=video_10m,
            batch_mode="segments",
            size_value=10,
            overlap_ms=2000,
            segment_ranges=[
                (index * 5000, (index + 1) * 5000) for index in range(120)
            ],
        )
        self.assertGreater(len(batches_seg), 0)
        self.assertEqual(batches_seg[0].start_ms, 0)
        self.assertEqual(batches_seg[0].end_ms, 52000)

    def test_12_real_whisper_timestamp_behavior(self):
        """A zero-based temporary WAV is shifted once onto the video timeline."""
        class LocalTimestampModel:
            def __init__(self):
                self.options = None

            def transcribe(self, path, **options):
                self.options = options
                segment = types.SimpleNamespace(
                    start=5.0,
                    end=8.0,
                    text="Local timestamp",
                    words=None,
                )
                return [segment], types.SimpleNamespace(language="en")

        request = replace(self.request, use_vad=False)
        service = FasterWhisperService(device="cpu")
        fake_model = LocalTimestampModel()
        service.model = fake_model
        service._extract_batch_audio = lambda _request, _batch: ("batch.wav", "")
        batch = SubtitleGenerationBatch(
            batch_id="batch_2",
            start_ms=300000,
            end_ms=602000,
            status="RUNNING",
            revision=0,
            created_at="now",
            updated_at="now",
        )

        result = service.transcribe_batch(request, batch, lambda: False)

        self.assertIsNone(result.error)
        self.assertEqual(
            (result.segments[0].start_ms, result.segments[0].end_ms),
            (305000, 308000),
        )
        self.assertNotIn("clip_timestamps", fake_model.options)
        self.assertFalse(fake_model.options["vad_filter"])

    def test_15_manual_subtitle_artifact_edit_is_detected_by_hash_guard(self):
        self.service.start_generation(self.request, 300000)
        artifact = self.project_service.artifact_store.get("sub_123")
        with open(artifact.path, "a", encoding="utf-8") as handle:
            handle.write("\n")

        with self.assertRaisesRegex(RuntimeError, "STALE_SUBTITLE_FILE"):
            self.service.resume_generation()

    def test_16_vad_batch_uses_local_audio_timestamps_and_shifts_once(self):
        class LocalTimestampModel:
            def transcribe(self, path, **options):
                self.path = path
                self.options = options
                segment = types.SimpleNamespace(
                    start=5.0,
                    end=8.0,
                    text="Local timestamp",
                    words=None,
                )
                return [segment], types.SimpleNamespace(language="en")

        request = replace(self.request, use_vad=True)
        service = FasterWhisperService(device="cpu")
        fake_model = LocalTimestampModel()
        service.model = fake_model
        service._extract_batch_audio = lambda _request, _batch: ("batch.wav", "")
        batch = SubtitleGenerationBatch(
            batch_id="batch_2",
            start_ms=300000,
            end_ms=602000,
            status="RUNNING",
            revision=0,
            created_at="now",
            updated_at="now",
        )

        result = service.transcribe_batch(request, batch, lambda: False)

        self.assertIsNone(result.error)
        self.assertEqual(
            (result.segments[0].start_ms, result.segments[0].end_ms),
            (305000, 308000),
        )
        self.assertNotIn("clip_timestamps", fake_model.options)
        self.assertTrue(fake_model.options["vad_filter"])

    def test_17_segment_generation_fills_next_timing_range_group_only(self):
        timing_path = os.path.join(self.test_dir, "timing.srt")
        with open(timing_path, "w", encoding="utf-8") as handle:
            handle.write(
                "1\n00:00:00,000 --> 00:00:10,000\n[empty]\n\n"
                "2\n00:00:10,000 --> 00:00:20,000\n[empty]\n\n"
                "3\n00:00:20,000 --> 00:00:30,000\n[empty]\n"
            )
        self.project_service.current_project.state.timing = types.SimpleNamespace(
            timing_artifact_id="timing_1"
        )
        self.project_service.artifact_store.register(
            types.SimpleNamespace(artifact_id="timing_1", path=timing_path)
        )
        request = replace(self.request, batch_mode="segments", batch_size_value=2)

        self.service.start_generation(request, 30000)

        self.assertEqual(len(self.service.current_batches), 1)
        self.assertEqual(
            (self.service.current_batches[0].start_ms, self.service.current_batches[0].end_ms),
            (0, 22000),
        )
        checkpoint = self.service.checkpoint_manager.load_checkpoint()
        self.assertEqual(checkpoint.timing_segment_cursor, 2)

        self.service.start_generation(
            replace(request, request_id="req_2"), 30000
        )

        self.assertEqual(len(self.service.current_batches), 1)
        self.assertEqual(
            (self.service.current_batches[0].start_ms, self.service.current_batches[0].end_ms),
            (20000, 30000),
        )

    def test_segment_generation_keeps_all_requested_timing_rows(self):
        """Five Timing slots remain five rows even when Whisper returns three texts."""
        timing_path = os.path.join(self.test_dir, "timing-five.srt")
        with open(timing_path, "w", encoding="utf-8") as handle:
            handle.write(
                "1\n00:00:00,000 --> 00:00:01,000\n[empty]\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\n[empty]\n\n"
                "3\n00:00:02,000 --> 00:00:03,000\n[empty]\n\n"
                "4\n00:00:03,000 --> 00:00:04,000\n[empty]\n\n"
                "5\n00:00:04,000 --> 00:00:05,000\n[empty]\n"
            )
        self.project_service.current_project.state.timing = types.SimpleNamespace(
            timing_artifact_id="timing-five"
        )
        self.project_service.artifact_store.register(
            types.SimpleNamespace(artifact_id="timing-five", path=timing_path)
        )

        def transcribe_three(_request, batch, _is_cancelled):
            return SubtitleGenerationResult(
                batch.batch_id,
                [
                    WhisperSegmentResult(100, 900, "one"),
                    WhisperSegmentResult(1200, 1800, "two"),
                    WhisperSegmentResult(3200, 3800, "four"),
                ],
            )

        self.whisper.transcribe_batch = transcribe_three
        request = replace(self.request, batch_mode="segments", batch_size_value=5)

        self.service.start_generation(request, 5000)

        artifact = self.project_service.artifact_store.get("sub_123")
        with open(artifact.path, "r", encoding="utf-8") as handle:
            rows = json.load(handle)["segments"]
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            [(row["start_ms"], row["end_ms"]) for row in rows],
            [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000), (4000, 5000)],
        )
        self.assertEqual([row["text"] for row in rows], ["one", "two", "", "four", ""])

    def test_segment_generation_fills_timing_artifact_without_dropping_future_rows(self):
        """A partial Full Subtitle run updates Timing rows instead of rebuilding from row 1."""
        timing_path = os.path.join(self.test_dir, "timing-four.srt")
        with open(timing_path, "w", encoding="utf-8") as handle:
            handle.write(
                "1\n00:00:00,000 --> 00:00:01,000\n[ Chưa có nội dung ]\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\n[ Chưa có nội dung ]\n\n"
                "3\n00:00:02,000 --> 00:00:03,000\n[ Chưa có nội dung ]\n\n"
                "4\n00:00:03,000 --> 00:00:04,000\n[ Chưa có nội dung ]\n"
            )
        self.project_service.current_project.state.timing = types.SimpleNamespace(
            timing_artifact_id="timing-four"
        )
        self.project_service.artifact_store.register(
            types.SimpleNamespace(artifact_id="timing-four", path=timing_path)
        )

        def transcribe_first_two(_request, batch, _is_cancelled):
            return SubtitleGenerationResult(
                batch.batch_id,
                [
                    WhisperSegmentResult(100, 900, "one"),
                    WhisperSegmentResult(1100, 1900, "two"),
                ],
            )

        self.whisper.transcribe_batch = transcribe_first_two
        request = replace(self.request, batch_mode="segments", batch_size_value=2)

        self.service.start_generation(request, 4000)

        artifact = self.project_service.artifact_store.get("sub_123")
        rows = self.service.artifact_service.load_data(artifact.path)["segments"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            [(row["start_ms"], row["end_ms"]) for row in rows],
            [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000)],
        )
        self.assertEqual([row["text"] for row in rows], ["one", "two", "", ""])

    def test_timing_mode_resume_routes_to_timing_pipeline(self):
        """Resume in Timing Draft must not invoke the subtitle checkpoint flow."""
        class ValueControl:
            def currentData(self):
                return "timing"

            def value(self):
                return 10

        class CapturingSignal:
            def __init__(self):
                self.calls = []

            def emit(self, *args):
                self.calls.append(args)

        class SubtitleService:
            def __init__(self):
                self.resume_calls = 0

            def resume_generation(self):
                self.resume_calls += 1

        panel = SubtitleGenerationPanel.__new__(SubtitleGenerationPanel)
        panel.cmb_mode = ValueControl()
        panel.spin_batch_val = ValueControl()
        panel.timing_resume_requested = CapturingSignal()
        panel.generation_service = SubtitleService()
        panel._set_ui_state_running = lambda: None

        panel._on_resume_clicked()

        self.assertEqual(
            panel.timing_resume_requested.calls,
            [(10, {"use_vad": True, "min_silence_ms": 500})],
        )
        self.assertEqual(panel.generation_service.resume_calls, 0)

    def test_timing_checkpoint_makes_resume_available_in_timing_mode(self):
        """A saved Timing checkpoint must drive Resume visibility in Timing Draft."""
        class ValueControl:
            def currentData(self):
                return "timing"

        class Button:
            def __init__(self):
                self.visible = None
                self.enabled = None

            def setVisible(self, value):
                self.visible = value

            def setEnabled(self, value):
                self.enabled = value

        class CheckpointManager:
            @staticmethod
            def load_checkpoint():
                return None

        class ProjectService:
            @staticmethod
            def load_timing_checkpoint():
                return types.SimpleNamespace(
                    timing_artifact_id="timing_1",
                    next_segment_index=11,
                    active_batch=None,
                )

        panel = SubtitleGenerationPanel.__new__(SubtitleGenerationPanel)
        panel.cmb_mode = ValueControl()
        panel.btn_resume = Button()
        panel.generation_service = types.SimpleNamespace(
            is_running=False,
            checkpoint_manager=CheckpointManager(),
            project_service=ProjectService(),
        )

        panel.check_resumable_state()

        self.assertTrue(panel.btn_resume.visible)
        self.assertTrue(panel.btn_resume.enabled)

    def test_timing_mode_keeps_segment_batch_selection_when_generating(self):
        """Timing Draft must send the selected segment count without resetting mode."""
        class Control:
            def __init__(self, data=None, value=10):
                self.data = data
                self.value_data = value
                self.enabled = None
                self.index_changes = []
                self.checked = None
                self.text = None

            def currentData(self):
                return self.data

            def value(self):
                return self.value_data

            def setEnabled(self, value):
                self.enabled = value

            def setCurrentIndex(self, index):
                self.index_changes.append(index)

            def setChecked(self, value):
                self.checked = value

            def setText(self, value):
                self.text = value

            def setRange(self, minimum, maximum):
                self.range = (minimum, maximum)

            def setSuffix(self, suffix):
                self.suffix = suffix

            def setValue(self, value):
                self.value_data = value

            @staticmethod
            def model():
                return types.SimpleNamespace(
                    item=lambda _index: types.SimpleNamespace(
                        setEnabled=lambda _value: None
                    )
                )

        class CapturingSignal:
            def __init__(self):
                self.calls = []

            def emit(self, *args):
                self.calls.append(args)

        panel = SubtitleGenerationPanel.__new__(SubtitleGenerationPanel)
        panel.cmb_mode = Control(data="timing")
        panel.cmb_batch_mode = Control(data="segments")
        panel.spin_batch_val = Control(value=10)
        panel.model_group = Control()
        panel.cmb_model = Control()
        panel.cmb_compute = Control()
        panel.cmb_language = Control()
        panel.chk_word_timestamps = Control()
        panel.chk_vad = Control()
        panel.timing_start_requested = CapturingSignal()
        panel.video_duration_ms = 600000
        panel.btn_resume = Control()
        panel.generation_service = types.SimpleNamespace(project_service=None)
        panel.check_resumable_state = lambda: None
        panel._set_ui_state_running = lambda: None

        panel._on_mode_changed()
        panel._on_batch_mode_changed()
        panel._on_generate_clicked()

        self.assertTrue(panel.cmb_batch_mode.enabled)
        self.assertEqual(panel.cmb_batch_mode.index_changes, [])
        self.assertEqual(
            panel.timing_start_requested.calls,
            [(10, {"use_vad": True, "min_silence_ms": 500})],
        )

    def test_timing_generate_continues_from_existing_checkpoint(self):
        """Generate resumes Timing at the checkpoint instead of restarting at segment 1."""
        class ModeControl:
            def currentData(self):
                return "timing"

        class ValueControl:
            def value(self):
                return 10

        class CapturingSignal:
            def __init__(self):
                self.calls = []

            def emit(self, *args):
                self.calls.append(args)

        project = types.SimpleNamespace(
            state=types.SimpleNamespace(timing=types.SimpleNamespace(status="IDLE"))
        )
        project_service = types.SimpleNamespace(
            current_project=project,
            load_timing_checkpoint=lambda: types.SimpleNamespace(
                timing_artifact_id="timing_1",
                active_batch=None,
                next_segment_index=11,
            ),
        )
        panel = SubtitleGenerationPanel.__new__(SubtitleGenerationPanel)
        panel.cmb_mode = ModeControl()
        panel.spin_batch_val = ValueControl()
        panel.video_duration_ms = 600000
        panel.timing_start_requested = CapturingSignal()
        panel.timing_resume_requested = CapturingSignal()
        panel.generation_service = types.SimpleNamespace(project_service=project_service)
        panel._set_ui_state_running = lambda: None

        panel._on_generate_clicked()

        self.assertEqual(panel.timing_start_requested.calls, [])
        self.assertEqual(
            panel.timing_resume_requested.calls,
            [(10, {"use_vad": True, "min_silence_ms": 500})],
        )

    def test_asr_allows_segment_batching_from_draft_timing_artifact(self):
        """Full Subtitle may use real Timing ranges before Timing reaches READY."""
        class ModeControl:
            def currentData(self):
                return "asr"

        class BatchModeControl:
            def __init__(self):
                self.item_enabled = None

            def model(self):
                return types.SimpleNamespace(
                    item=lambda _index: types.SimpleNamespace(
                        setEnabled=self._set_item_enabled
                    )
                )

            def _set_item_enabled(self, enabled):
                self.item_enabled = enabled

            @staticmethod
            def currentData():
                return "time"

        timing_artifact = types.SimpleNamespace(path="timing.srt")
        project_service = types.SimpleNamespace(
            current_project=types.SimpleNamespace(
                state=types.SimpleNamespace(
                    timing_status="DRAFT",
                    timing=types.SimpleNamespace(timing_artifact_id="timing_1"),
                )
            ),
            artifact_store=types.SimpleNamespace(get=lambda artifact_id: timing_artifact),
        )
        panel = SubtitleGenerationPanel.__new__(SubtitleGenerationPanel)
        panel.cmb_mode = ModeControl()
        panel.cmb_batch_mode = BatchModeControl()
        panel.generation_service = types.SimpleNamespace(project_service=project_service)

        panel.refresh_batch_mode_availability()

        self.assertTrue(panel.cmb_batch_mode.item_enabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
