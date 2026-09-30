import copy
import unittest
from unittest.mock import patch

from tests import test_generation_range
from core.subtitle_generation.subtitle_generation_result import (
    SubtitleGenerationResult, WhisperSegmentResult,
)


class TestCoverageAuthority(unittest.TestCase):
    def setUp(self):
        test_generation_range.TestRangeGenerationTransaction.setUp(self)
        self.request.range_start_ms = 1000
        self.request.range_end_ms = 1500
        self.artifact = self.service.artifact_service.get_or_create_artifact()
        self.saved = [{"id": "A", "start_ms": 1000, "end_ms": 3000, "text": "old"}]
        self.persist(self.saved)
        self.dirty_calls.clear()
        self.errors = []
        self.service.on_error = self.errors.append
        self.asr_calls = []

        def transcribe(request, batch, cancelled):
            self.asr_calls.append((batch.start_ms, batch.end_ms))
            return SubtitleGenerationResult(
                batch.batch_id, [WhisperSegmentResult(batch.start_ms, batch.end_ms, "new")]
            )
        self.whisper.transcribe_batch = transcribe

    def persist(self, rows):
        self.service.artifact_service._save_atomic(
            self.artifact.path, {"version": 1, "segments": rows}
        )

    def rows(self):
        return self.service.artifact_service.load_data(self.artifact.path)["segments"]

    def generate(self, runtime):
        self.service.start_generation(self.request, 10000, existing_segments=runtime)

    def assert_success(self, runtime):
        before = copy.deepcopy(runtime)
        self.generate(runtime)
        self.assertEqual(self.errors, [])
        self.assertEqual(self.asr_calls, [(1000, 1500)])
        self.assertEqual(len(self.dirty_calls), 1)
        self.assertEqual([row for row in self.rows() if row["id"] == "A"], before)
        self.assertEqual(runtime, before)
        self.assertEqual(len(self.rows()), len(runtime) + 1)

    def test_unsaved_trim_allows_gap_and_preserves_current_metadata(self):
        self.assert_success([dict(self.saved[0], start_ms=1500, text="edited", metadata={"keep": True})])

    def test_real_resize_command_then_generation_without_save(self):
        from core.timeline.timeline_commands import ResizeStartCommand
        from core.timeline.timeline_data_provider import TimelineDataProvider
        from types import SimpleNamespace
        current = copy.deepcopy(self.saved)
        self.project_service.current_project.state.active_artifact_id = None
        editor = SimpleNamespace(all_segments=current)
        provider = TimelineDataProvider()
        provider.load_runtime_data(editor.all_segments, 10000)
        command = ResizeStartCommand(self.project_service, provider, "A", 500)
        self.assertTrue(command.execute())
        self.assertEqual(current[0]["start_ms"], 1500)
        self.assertEqual(self.rows(), self.saved)
        self.dirty_calls.clear()
        self.service.range_segments_provider = lambda: editor.all_segments
        self.generate(editor.all_segments)
        self.assertEqual(self.errors, [])
        self.assertEqual(self.asr_calls, [(1000, 1500)])
        self.assertEqual(self.rows()[1], current[0])
        self.assertEqual(len(self.dirty_calls), 1)

    def test_unsaved_extend_blocks_gap(self):
        self.persist([dict(self.saved[0], start_ms=1500)])
        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.generate(self.saved)
        self.assertEqual(self.asr_calls, [])

    def test_unsaved_move_out_allows_generation(self):
        self.assert_success([dict(self.saved[0], start_ms=3000, end_ms=5000)])

    def test_unsaved_move_in_blocks_generation(self):
        self.persist([dict(self.saved[0], start_ms=3000, end_ms=5000)])
        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.generate(self.saved)

    def test_authoritative_empty_does_not_resurrect_deleted_rows(self):
        self.assert_success([])

    def test_new_unsaved_subtitle_blocks_generation(self):
        self.persist([])
        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.generate(self.saved)

    def test_unavailable_runtime_falls_back_to_artifact(self):
        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.generate(None)
        self.assertEqual(self.asr_calls, [])

    def test_provider_is_authority_at_start_and_commit(self):
        current = [dict(self.saved[0], start_ms=1500)]
        self.service.range_segments_provider = lambda: current
        self.generate(self.saved)
        self.assertEqual(self.errors, [])
        self.assertEqual(self.rows()[1], current[0])

    def test_unavailable_provider_uses_artifact_not_start_snapshot(self):
        self.service.range_segments_provider = lambda: None
        with self.assertRaisesRegex(ValueError, "OVERLAPS_SUBTITLE"):
            self.generate([])

    def test_runtime_changes_during_asr_rejects_commit_without_disk_change(self):
        current = [dict(self.saved[0], start_ms=1500)]
        self.service.range_segments_provider = lambda: current
        original = self.whisper.transcribe_batch
        def transcribe(*args):
            result = original(*args)
            current[0]["start_ms"] = 1200
            return result
        self.whisper.transcribe_batch = transcribe
        self.generate(current)
        self.assertTrue(any(error.startswith("STALE_RANGE_CONFLICT:") for error in self.errors))
        self.assertEqual(self.rows(), self.saved)
        self.assertEqual(self.dirty_calls, [])
        self.assertEqual(len(self.asr_calls), 1)

    def test_live_supplied_rows_are_revalidated_without_provider(self):
        current = [dict(self.saved[0], start_ms=1500)]
        original = self.whisper.transcribe_batch
        def transcribe(*args):
            result = original(*args)
            current[0]["start_ms"] = 1200
            return result
        self.whisper.transcribe_batch = transcribe
        self.generate(current)
        self.assertTrue(any(error.startswith("STALE_RANGE_CONFLICT:") for error in self.errors))
        self.assertEqual(self.rows(), self.saved)

    def test_wrong_project_rejected_before_asr(self):
        self.request.project_id = "wrong"
        with self.assertRaisesRegex(ValueError, "Project ID"):
            self.generate([])
        self.assertEqual(self.asr_calls, [])

    def test_wrong_source_rejected_before_asr(self):
        self.request.source_fingerprint = "wrong"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.generate([])
        self.assertEqual(self.asr_calls, [])

    def test_external_artifact_change_still_rejects_commit(self):
        current = [dict(self.saved[0], start_ms=1500)]
        original = self.whisper.transcribe_batch
        def transcribe(*args):
            result = original(*args)
            self.persist([dict(self.saved[0], text="external")])
            return result
        self.whisper.transcribe_batch = transcribe
        self.generate(current)
        self.assertTrue(any(error.startswith("STALE_SUBTITLE_FILE:") for error in self.errors))
        self.assertEqual(self.dirty_calls, [])

    def test_artifact_identity_change_during_asr_rejects_commit(self):
        original = self.whisper.transcribe_batch
        def transcribe(*args):
            result = original(*args)
            self.project_service.current_project.state.subtitle_artifact_id = "other"
            return result
        self.whisper.transcribe_batch = transcribe
        self.generate([])
        self.assertTrue(any("identity changed" in error for error in self.errors))
        self.assertEqual(self.rows(), self.saved)
        self.assertEqual(self.dirty_calls, [])

    def test_artifact_revision_change_during_asr_rejects_commit(self):
        original = self.whisper.transcribe_batch
        def transcribe(*args):
            result = original(*args)
            self.artifact.revision += 1
            return result
        self.whisper.transcribe_batch = transcribe
        self.generate([])
        self.assertTrue(any("revision changed" in error for error in self.errors))
        self.assertEqual(self.rows(), self.saved)
        self.assertEqual(self.dirty_calls, [])

    def test_headless_fallback_preserves_existing_artifact_rows_on_success(self):
        self.request.range_start_ms = 3000
        self.request.range_end_ms = 3500
        self.generate(None)
        self.assertEqual(self.errors, [])
        self.assertEqual(self.rows()[0], self.saved[0])
        self.assertEqual(len(self.rows()), 2)

    def test_asr_failure_preserves_runtime_and_artifact(self):
        current = [dict(self.saved[0], start_ms=1500)]
        self.whisper.transcribe_batch = lambda request, batch, cancelled: SubtitleGenerationResult(batch.batch_id, [], "failure")
        self.generate(current)
        self.assertTrue(self.errors)
        self.assertEqual(self.rows(), self.saved)
        self.assertEqual(current[0]["start_ms"], 1500)
        self.assertEqual(self.dirty_calls, [])

    def test_reconciliation_runs_once_after_one_asr(self):
        from core.subtitle_generation.generation_timing_reconciler import reconcile_generated_timing
        with patch("core.subtitle_generation.generation_service.reconcile_generated_timing", wraps=reconcile_generated_timing) as reconcile:
            self.generate([])
        self.assertEqual(len(self.asr_calls), 1)
        self.assertEqual(reconcile.call_count, 1)
        self.assertEqual(self.errors, [])


class TestEditorCoverageBinding(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from ui.Gui import MainWindow
        self.resolve = MainWindow._current_range_segments
        self.item = {"project_id": "P", "project_root": "root"}
        self.project = SimpleNamespace(state=SimpleNamespace(subtitle_artifact_id="A"))
        self.window = SimpleNamespace(
            project_service=SimpleNamespace(
                current_project=self.project,
                is_current_project_for_video=lambda path: path == "media",
                artifact_store=SimpleNamespace(get=lambda key: SimpleNamespace(path="current.sub.json")),
            ),
            queue_mgr=SimpleNamespace(
                active_vid="media", active_item_key="item",
                get_item=lambda key: self.item,
                get_active_data=lambda: ("media", "current_shadow.srt"),
            ),
            _queue_project_identity_matches=lambda project_id, root: project_id == "P" and root == "root",
            sub_editor=SimpleNamespace(all_segments=[], srt_path="current_shadow.srt"),
        )

    def test_loaded_empty_editor_is_authoritative(self):
        self.assertIs(self.resolve(self.window), self.window.sub_editor.all_segments)

    def test_unhydrated_editor_is_unavailable(self):
        self.window.sub_editor.srt_path = None
        self.assertIsNone(self.resolve(self.window))

    def test_wrong_project_binding_is_unavailable(self):
        self.item["project_id"] = "other"
        self.assertIsNone(self.resolve(self.window))

    def test_wrong_media_is_unavailable(self):
        self.window.queue_mgr.active_vid = "other"
        self.assertIsNone(self.resolve(self.window))

    def test_other_editor_file_is_unavailable(self):
        self.window.sub_editor.srt_path = "other.srt"
        self.assertIsNone(self.resolve(self.window))

    def test_unbound_queue_is_unavailable(self):
        self.item.clear()
        self.assertIsNone(self.resolve(self.window))
