import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from dataclasses import replace

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
    qt_core.Signal = _Signal
    qt_core.Slot = lambda *args, **kwargs: (lambda function: function)
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qt_core
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qt_core

from core.artifacts.artifact_types import ArtifactType
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

    def test_12_planner_supports_segment_based_batches(self):
        timing_ranges = [
            (index * 5000, (index + 1) * 5000) for index in range(20)
        ]
        batches = SubtitleGenerationPlanner.create_plan(
            100000,
            "segments",
            10,
            2000,
            segment_ranges=timing_ranges,
        )
        self.assertEqual(len(batches), 2)
        self.assertEqual((batches[0].start_ms, batches[0].end_ms), (0, 52000))
        self.assertEqual((batches[1].start_ms, batches[1].end_ms), (48000, 100000))

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

    def test_14_faster_whisper_clip_timestamps_are_not_shifted_twice(self):
        """A clipped source returns absolute timestamps from Faster-Whisper."""
        class AbsoluteTimestampModel:
            def __init__(self):
                self.options = None

            def transcribe(self, path, **options):
                self.options = options
                segment = types.SimpleNamespace(
                    start=305.0,
                    end=308.0,
                    text="Absolute timestamp",
                    words=None,
                )
                return [segment], types.SimpleNamespace(language="en")

        request = replace(self.request, use_vad=False)
        service = FasterWhisperService(device="cpu")
        fake_model = AbsoluteTimestampModel()
        service.model = fake_model
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
        self.assertEqual(fake_model.options["clip_timestamps"], [300.0, 602.0])

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

    def test_17_service_segment_mode_reads_timing_artifact_ranges(self):
        timing_path = os.path.join(self.test_dir, "timing.srt")
        with open(timing_path, "w", encoding="utf-8") as handle:
            handle.write(
                "1\n00:00:00,000 --> 00:00:10,000\n[empty]\n\n"
                "2\n00:00:10,000 --> 00:00:20,000\n[empty]\n"
            )
        self.project_service.current_project.state.timing = types.SimpleNamespace(
            timing_artifact_id="timing_1"
        )
        self.project_service.artifact_store.register(
            types.SimpleNamespace(artifact_id="timing_1", path=timing_path)
        )
        request = replace(self.request, batch_mode="segments", batch_size_value=1)

        self.service.start_generation(request, 30000)

        self.assertEqual(len(self.service.current_batches), 2)
        self.assertEqual(
            (self.service.current_batches[0].start_ms, self.service.current_batches[0].end_ms),
            (0, 12000),
        )
        self.assertEqual(
            (self.service.current_batches[1].start_ms, self.service.current_batches[1].end_ms),
            (8000, 22000),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
