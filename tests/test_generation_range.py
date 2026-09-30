import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace


class TestGenerationRangeContract(unittest.TestCase):
    def _api(self):
        import importlib
        import importlib.util

        module_name = "core.subtitle_generation.generation_range"
        self.assertIsNotNone(
            importlib.util.find_spec(module_name), "range contract module is not implemented"
        )
        generation_range = importlib.import_module(module_name)

        validate = getattr(generation_range, "validate_generation_range", None)
        parse = getattr(generation_range, "parse_timecode_ms", None)
        self.assertTrue(callable(validate), "range validator is not implemented")
        self.assertTrue(callable(parse), "range time parser is not implemented")
        return validate, parse

    def test_generation_request_can_carry_one_uncovered_range(self):
        from dataclasses import fields

        from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest

        names = {field.name for field in fields(SubtitleGenerationRequest)}
        self.assertTrue({"range_start_ms", "range_end_ms"}.issubset(names))

    def test_manual_time_uses_project_millisecond_format(self):
        _validate, parse = self._api()
        self.assertEqual(parse("00:00:10,000"), 10000)
        with self.assertRaises(ValueError):
            parse("10 seconds")
        with self.assertRaises(ValueError):
            parse("00:60:00,000")
        with self.assertRaises(ValueError):
            parse("00:00:60,000")

    def test_uncovered_range_and_touching_edges_are_valid(self):
        validate, _parse = self._api()
        segments = [
            {"start_ms": 5000, "end_ms": 10000, "text": ""},
            {"start_ms": 15000, "end_ms": 20000, "text": "spoken"},
        ]
        self.assertEqual(validate(10000, 15000, 30000, segments).status.value, "VALID")
        self.assertEqual(validate(0, 5000, 30000, segments).status.value, "VALID")
        self.assertEqual(validate(20000, 21000, 30000, segments).status.value, "VALID")

    def test_positive_overlap_with_empty_text_still_blocks(self):
        validate, _parse = self._api()
        result = validate(
            9999,
            12000,
            20000,
            [{"start_ms": 5000, "end_ms": 10000, "text": ""}],
        )
        self.assertEqual(result.status.value, "OVERLAPS_SUBTITLE")

    def test_range_crossing_coverage_and_invalid_boundaries_are_rejected(self):
        validate, _parse = self._api()
        coverage = [{"start_ms": 10000, "end_ms": 12000, "text": "x"}]
        self.assertEqual(validate(9000, 13000, 30000, coverage).status.value, "OVERLAPS_SUBTITLE")
        self.assertEqual(validate(-1, 1000, 30000, []).status.value, "OUT_OF_BOUNDS")
        self.assertEqual(validate(0, 30001, 30000, []).status.value, "OUT_OF_BOUNDS")
        self.assertEqual(validate(1000, 1000, 30000, []).status.value, "EMPTY_OR_REVERSED")
        self.assertEqual(validate(2000, 1000, 30000, []).status.value, "EMPTY_OR_REVERSED")
        self.assertEqual(validate(0, 1000, 0, []).status.value, "NO_MEDIA")

    def test_gap_selection_and_manual_time_share_timeline_range(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.timeline.timeline_widget import TimelineWidget

        self.assertTrue(hasattr(TimelineWidget, "set_generation_range"))
        app = QApplication.instance() or QApplication([])
        timeline = TimelineWidget()
        timeline.load_project_data(
            20000,
            [SimpleNamespace(segment_id="covered", start_ms=0, end_ms=10000, text="")],
        )
        _ = app

        timeline.select_gap(timeline.container.track.gaps[0])
        self.assertEqual(
            (timeline.generation_range.start_ms, timeline.generation_range.end_ms),
            (10000, 20000),
        )
        self.assertEqual(timeline.container.start_range_edit.text(), "00:00:10,000")
        timeline.container.start_range_edit.setText("00:00:12,000")
        timeline.container.end_range_edit.setText("00:00:16,000")
        timeline._on_manual_range_changed()
        self.assertEqual(
            (timeline.generation_range.start_ms, timeline.generation_range.end_ms),
            (12000, 16000),
        )
        self.assertEqual(timeline.container.waveform._selected_range_ms, (12000, 16000))
        self.assertTrue(timeline.container.generate_gap_button.isEnabled())
        timeline.load_project_data(30000, [])
        self.assertIsNone(timeline.generation_range)
        self.assertFalse(timeline.container.generate_gap_button.isEnabled())

    def test_manual_range_crossing_timing_only_subtitle_is_blocked(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.timeline.timeline_widget import TimelineWidget

        app = QApplication.instance() or QApplication([])
        timeline = TimelineWidget()
        timeline.load_project_data(
            30000,
            [SimpleNamespace(segment_id="empty", start_ms=5000, end_ms=10000, text="")],
        )
        timeline.container.start_range_edit.setText("00:00:09,999")
        timeline.container.end_range_edit.setText("00:00:12,000")
        timeline._on_manual_range_changed()

        self.assertEqual(timeline.range_validation.status.value, "OVERLAPS_SUBTITLE")
        self.assertFalse(timeline.container.generate_gap_button.isEnabled())
        self.assertIn("đang chứa phụ đề", timeline.container.range_validation.text())
        _ = app

    def test_generation_busy_state_disables_generate(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.timeline.timeline_widget import TimelineWidget

        app = QApplication.instance() or QApplication([])
        timeline = TimelineWidget()
        timeline.load_project_data(20000, [])
        timeline.set_generation_range(5000, 10000)
        self.assertTrue(timeline.container.generate_gap_button.isEnabled())
        timeline.set_generation_busy(True)
        self.assertFalse(timeline.container.generate_gap_button.isEnabled())
        timeline.set_generation_busy(False)
        self.assertTrue(timeline.container.generate_gap_button.isEnabled())
        _ = app

    def test_shift_drag_on_waveform_selects_visual_range_without_seeking(self):
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from core.timeline.timeline_controller import TimelineController
        from core.timeline.timeline_data_provider import TimelineDataProvider
        from ui.timeline.timeline_widget import TimelineWidget

        app = QApplication.instance() or QApplication([])
        timeline = TimelineWidget()
        timeline.resize(700, 240)
        timeline.load_project_data(30000, [])
        provider = TimelineDataProvider()
        provider.load_runtime_data([], 30000)
        controller = TimelineController(SimpleNamespace(), timeline, provider)
        waveform = timeline.container.waveform
        waveform.resize(3000, 100)
        waveform.show()
        seeks = []
        timeline.seek_requested.connect(seeks.append)

        QTest.mousePress(waveform, Qt.LeftButton, Qt.ShiftModifier, QPoint(1200, 50))
        QTest.mouseMove(waveform, QPoint(1600, 50), 10)
        QTest.mouseRelease(waveform, Qt.LeftButton, Qt.ShiftModifier, QPoint(1600, 50))

        self.assertEqual(
            (timeline.generation_range.start_ms, timeline.generation_range.end_ms),
            (12000, 16000),
        )
        self.assertEqual(waveform._selected_range_ms, (12000, 16000))
        self.assertEqual(seeks, [])
        controller.deleteLater()
        _ = app


class TestRangeGenerationTransaction(unittest.TestCase):
    def setUp(self):
        from tests.test_subtitle_generation import MockProjectService, MockWhisperService
        from core.subtitle_generation.generation_service import SubtitleGenerationService
        from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
        from workers.subtitle_generation_worker import SubtitleGenerationWorker

        self.test_dir = tempfile.mkdtemp()
        self.project_service = MockProjectService(self.test_dir)
        self.whisper = MockWhisperService()
        self.service = SubtitleGenerationService(self.whisper, self.project_service)
        self._worker_start = SubtitleGenerationWorker.start
        SubtitleGenerationWorker.start = lambda worker: worker.run()
        self.addCleanup(lambda: setattr(SubtitleGenerationWorker, "start", self._worker_start))
        self.addCleanup(lambda: shutil.rmtree(self.test_dir, ignore_errors=True))
        self.request = SubtitleGenerationRequest(
            request_id="range-1",
            project_id="proj_123",
            source_fingerprint="video_hash_123",
            video_path="dummy.mp4",
            model_size="tiny",
            compute_type="int8",
            language=None,
            use_vad=True,
            min_silence_ms=500,
            word_timestamps=False,
        )
        self.request.range_start_ms = 3000
        self.request.range_end_ms = 8000
        self.dirty_calls = []
        self.project_service.mark_dirty = lambda: self.dirty_calls.append(True)

    def test_uncovered_range_generates_one_batch_and_preserves_chronological_subtitles(self):
        from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest

        self.assertTrue(hasattr(SubtitleGenerationRequest, "range_start_ms"))
        existing = [
            {"id": "before", "start_ms": 0, "end_ms": 3000, "text": "before", "metadata": {"style": "keep"}},
            {"id": "after", "start_ms": 8000, "end_ms": 10000, "text": "after"},
        ]
        self.service.start_generation(self.request, 10000, existing_segments=existing)

        artifact = self.project_service.artifact_store.get("sub_123")
        rows = self.service.artifact_service.load_data(artifact.path)["segments"]
        self.assertEqual(self.whisper.call_count, 1)
        self.assertEqual(
            (self.service.current_batches[0].start_ms, self.service.current_batches[0].end_ms),
            (3000, 8000),
        )
        self.assertEqual(rows[0], existing[0])
        self.assertEqual((rows[1]["start_ms"], rows[1]["end_ms"]), (3100, 5000))
        self.assertEqual((rows[2]["id"], rows[2]["start_ms"], rows[2]["end_ms"]), ("after", 8000, 10000))
        self.assertEqual(len(self.dirty_calls), 1)
        from core.timeline.gaps import find_timeline_gaps

        recomputed = find_timeline_gaps(
            10000,
            [
                SimpleNamespace(
                    segment_id=row["id"],
                    start_ms=row["start_ms"],
                    end_ms=row["end_ms"],
                )
                for row in rows
            ],
        )
        self.assertEqual(
            [(gap.start_ms, gap.end_ms) for gap in recomputed],
            [(3000, 3100), (5000, 8000)],
        )

    def test_range_audio_adapter_restores_local_asr_timestamps_once(self):
        from types import SimpleNamespace

        from core.subtitle_generation.faster_whisper_service import FasterWhisperService
        from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch

        class Model:
            def transcribe(self, _path, **_options):
                return [SimpleNamespace(start=0.25, end=2.0, text="local", words=None)], SimpleNamespace(language="en")

        service = FasterWhisperService(device="cpu")
        service.model = Model()
        seen = []
        service._extract_batch_audio = lambda _request, batch: (seen.append((batch.start_ms, batch.end_ms)) or ("clip.wav", ""))
        batch = SubtitleGenerationBatch("range", 12000, 15000, "PENDING", 0, "now", "now")

        result = service.transcribe_batch(self.request, batch, lambda: False)

        self.assertEqual(seen, [(12000, 15000)])
        self.assertEqual((result.segments[0].start_ms, result.segments[0].end_ms), (12250, 14000))

    def test_cancellation_before_worker_result_leaves_no_artifact_or_checkpoint(self):
        from workers.subtitle_generation_worker import SubtitleGenerationWorker

        SubtitleGenerationWorker.start = lambda _worker: None
        self.service.start_generation(self.request, 10000, existing_segments=[])
        self.service.cancel_generation()

        self.assertIsNone(self.project_service.artifact_store.get("sub_123"))
        self.assertEqual(self.dirty_calls, [])
        checkpoint = os.path.join(self.test_dir, "artifacts", "subtitle_generation", "checkpoint.json")
        self.assertFalse(os.path.exists(checkpoint))

    def test_asr_failure_leaves_existing_artifact_and_revision_unchanged(self):
        from core.subtitle_generation.subtitle_generation_result import SubtitleGenerationResult

        self.service.start_generation(
            __import__("dataclasses").replace(
                self.request, range_start_ms=None, range_end_ms=None
            ),
            3000,
        )
        artifact = self.project_service.artifact_store.get("sub_123")
        before_data = self.service.artifact_service.load_data(artifact.path)
        before_revision = artifact.revision
        before_dirty = len(self.dirty_calls)
        self.whisper.transcribe_batch = lambda _request, batch, _cancel: SubtitleGenerationResult(
            batch.batch_id, [], "mock inference failure"
        )

        self.service.start_generation(self.request, 10000, existing_segments=[])

        self.assertEqual(self.service.artifact_service.load_data(artifact.path), before_data)
        self.assertEqual(artifact.revision, before_revision)
        self.assertEqual(len(self.dirty_calls), before_dirty)

    def test_empty_asr_result_does_not_create_artifact(self):
        from core.subtitle_generation.subtitle_generation_result import SubtitleGenerationResult

        self.whisper.transcribe_batch = lambda _request, batch, _cancel: SubtitleGenerationResult(
            batch.batch_id, []
        )
        errors = []
        self.service.on_error = errors.append

        self.service.start_generation(self.request, 10000, existing_segments=[])

        self.assertIsNone(self.project_service.artifact_store.get("sub_123"))
        self.assertEqual(self.dirty_calls, [])
        self.assertTrue(errors)

    def test_overlap_is_rejected_before_model_or_persistence_changes(self):
        import inspect

        existing = [{"id": "occupied", "start_ms": 5000, "end_ms": 7000, "text": ""}]

        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.service.start_generation(self.request, 10000, existing_segments=existing)

        self.assertEqual(self.whisper.call_count, 0)
        self.assertIsNone(self.project_service.artifact_store.get("sub_123"))
        self.assertEqual(self.dirty_calls, [])

    def test_asr_result_outside_range_does_not_create_artifact_or_checkpoint(self):
        from core.subtitle_generation.subtitle_generation_result import SubtitleGenerationResult, WhisperSegmentResult

        self.whisper.transcribe_batch = lambda _request, batch, _cancel: SubtitleGenerationResult(
            batch.batch_id, [WhisperSegmentResult(7900, 8100, "outside")]
        )
        errors = []
        self.service.on_error = errors.append
        self.service.start_generation(self.request, 10000, existing_segments=[])

        checkpoint_path = self.service.checkpoint_manager._get_checkpoint_path()
        self.assertEqual(self.project_service.current_project.state.subtitle_artifact_id, "sub_123")
        self.assertIsNone(self.project_service.artifact_store.get("sub_123"))
        self.assertFalse(os.path.exists(checkpoint_path))
        self.assertEqual(self.dirty_calls, [])
        self.assertTrue(any("TIMING_RECONCILIATION_REQUIRED" in error for error in errors))
