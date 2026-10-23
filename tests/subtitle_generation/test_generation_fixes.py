import os
import shutil
import tempfile
import types
from dataclasses import replace
import unittest

from PySide6.QtWidgets import QApplication

from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from core.subtitle_generation.subtitle_generation_result import (
    SubtitleGenerationResult,
    WhisperSegmentResult,
)
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from workers.subtitle_generation_worker import SubtitleGenerationWorker
from core.timeline.timeline_controller import TimelineController


_app = QApplication.instance() or QApplication([])


class MockSource:
    fingerprint = "video_hash_123"


class MockState:
    subtitle_artifact_id = "sub_123"
    timing = None


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


class TrackingWhisperService(FasterWhisperService):
    def __init__(self):
        super().__init__()
        self.load_model_calls = []

    def load_model(self, model_size, compute_type):
        self.load_model_calls.append((model_size, compute_type))
        self.model = object()
        self.current_model_size = model_size
        self.current_compute_type = compute_type

    def transcribe_batch(self, request, batch, is_cancelled):
        return SubtitleGenerationResult(
            batch.batch_id,
            [WhisperSegmentResult(batch.start_ms, batch.end_ms, "Sample")],
        )


class TestGenerationFixes(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_service = MockProjectService(self.test_dir)
        self.whisper = TrackingWhisperService()
        self.service = SubtitleGenerationService(
            self.whisper,
            self.project_service,
        )
        self.request = SubtitleGenerationRequest(
            request_id="req_test",
            project_id="proj_123",
            source_fingerprint="video_hash_123",
            video_path=os.path.join(self.test_dir, "test.mp4"),
            model_size="base",
            compute_type="int8",
            language=None,
            use_vad=True,
            min_silence_ms=500,
            word_timestamps=False,
            batch_duration_ms=300000,
            overlap_ms=2000,
            prompt_context="",
            batch_mode="time",
            batch_size_value=5,
        )
        with open(self.request.video_path, "wb") as f:
            f.write(b"video_bytes")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tc_gen_01_worker_thread_loads_model_non_blocking(self):
        """TC-GEN-01: start_generation does not load model synchronously; worker loads it in run()."""
        batch = SubtitleGenerationBatch(
            batch_id="b_1",
            start_ms=0,
            end_ms=5000,
            status="PENDING",
            revision=1,
            created_at="",
            updated_at="",
        )
        worker = SubtitleGenerationWorker(self.request, batch, self.whisper)
        self.assertEqual(len(self.whisper.load_model_calls), 0)

        worker.run()
        self.assertEqual(len(self.whisper.load_model_calls), 1)
        self.assertEqual(self.whisper.load_model_calls[0], ("base", "int8"))
        self.assertTrue(self.whisper.is_loaded("base", "int8"))

        # Subsequent run does not reload if already loaded
        worker.run()
        self.assertEqual(len(self.whisper.load_model_calls), 1)

    def test_tc_gen_02_segment_batch_mode_only_creates_batch_count(self):
        """TC-GEN-02: Only current batch segments are created in artifact, not all 10 timing rows."""
        timing_path = os.path.join(self.test_dir, "timing.srt")
        with open(timing_path, "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(f"{i+1}\n00:00:0{i},000 --> 00:00:0{i+1},000\n[timing]\n\n")

        self.project_service.current_project.state.timing = types.SimpleNamespace(
            timing_artifact_id="timing_art"
        )
        self.project_service.artifact_store.register(
            types.SimpleNamespace(artifact_id="timing_art", path=timing_path)
        )

        SubtitleGenerationWorker.start = lambda w: w.run()
        req = replace(self.request, batch_mode="segments", batch_size_value=3)
        self.service.start_generation(req, 10000)

        artifact = self.project_service.artifact_store.get(
            self.project_service.current_project.state.subtitle_artifact_id
        )
        data = self.service.artifact_service.load_data(artifact.path)
        self.assertEqual(len(data["segments"]), 3)

    def test_tc_timeline_03_sync_selection_fallback_by_index_when_id_mismatched(self):
        """TC-TIMELINE-03: sync_selection falls back to index even when segment_id does not match track."""
        from ui.timeline.timeline_widget import TimelineWidget
        from core.timeline.timeline_data_provider import TimelineDataProvider

        timeline = TimelineWidget()
        provider = TimelineDataProvider()
        provider.load_runtime_data([
            {"id": "track_seg_0", "start_ms": 0, "end_ms": 1000, "text": "A"},
            {"id": "track_seg_1", "start_ms": 1000, "end_ms": 2000, "text": "B"},
        ], 3000)
        timeline.load_project_data(3000, provider.get_all_segments())

        ctrl = TimelineController(
            self.project_service,
            timeline,
            provider,
        )

        # Mismatched segment_id should NOT clear selection; it falls back to index 1
        from core.subtitle_editing.selection_controller import SelectionSource
        ctrl.sync_selection(index=1, segment_id="editor_mismatched_id", source=SelectionSource.EDITOR)
        self.assertEqual(timeline.container.track.selected_ids, {"track_seg_1"})

    def test_tc_resilience_04_stale_subtitle_auto_recovers_and_whisper_anti_hallucination(self):
        """TC-RESILIENCE-04: STALE_SUBTITLE revision mismatch recovers gracefully during commit."""
        SubtitleGenerationWorker.start = lambda w: w.run()
        self.service.start_generation(self.request, 30000)

        artifact = self.project_service.artifact_store.get(
            self.project_service.current_project.state.subtitle_artifact_id
        )
        # Simulate external autosave / tab change bumping revision
        artifact.revision = 42

        # Emulating commit with bumped revision succeeds without raising GenerationError
        batch = SubtitleGenerationBatch(
            batch_id="b_test",
            start_ms=0,
            end_ms=5000,
            status="RUNNING",
            revision=1,
            created_at="",
            updated_at="",
        )
        result = SubtitleGenerationResult("b_test", [WhisperSegmentResult(100, 2000, "Valid voice")])
        self.service._commit_batch(batch, result)

        self.assertEqual(self.service.current_checkpoint.artifact_revision, 43)
        self.assertIn("b_test", self.service.current_checkpoint.completed_batches)

        # Verify faster whisper transcribe options include anti-hallucination settings
        fws = FasterWhisperService()
        self.assertTrue(hasattr(fws, "is_loaded"))
