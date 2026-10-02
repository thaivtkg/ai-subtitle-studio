import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestCanonicalSubtitleHydration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from core.services.project_service import ProjectService
        from core.subtitle_generation.subtitle_artifact_service import SubtitleArtifactService
        from ui.Gui import MainWindow
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        profile = patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "profile")})
        profile.start()
        self.addCleanup(profile.stop)
        self.media = self.root / "media.mp4"
        self.media.write_bytes(b"media")
        self.service = ProjectService()
        self.project = self.service.create_project(str(self.root / "project.ai-subtitle"), "A", str(self.media))
        self.artifacts = SubtitleArtifactService(self.service)
        self.row = {"id": "stable-A", "start_ms": 1000, "end_ms": 3000, "text": "hello",
                    "status": "approved", "words": [{"word": "hello", "start": 1.0, "end": 3.0}],
                    "metadata": {"source": "ASR"}, "extra": {"future": [1, 2]}}
        self.artifact = self.artifacts.create_artifact_with_data({"version": 1, "segments": [self.row]})
        self.window = MainWindow(project_service=self.service, media_import_service=MagicMock())
        self.window.video_player.load_video = MagicMock()
        self.window.video_player.sub_controller.load_srt = MagicMock()
        self.window.generation_panel.check_resumable_state = MagicMock()
        self.window._refresh_transcription_context_views = MagicMock()
        self.window._sync_subtitle_placement_from_project = MagicMock()
        self.shadow = self.window._on_generation_batch_sync()
        self.item = self.window.queue_mgr.ensure_project_binding(str(self.media), project_id=self.project.project_id,
                                                                project_root=self.service.project_dir)
        self.window.queue_mgr.set_srt_for_video(self.item, self.shadow)

    def tearDown(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
        self.window.autosave_coordinator.dispose()
        self.window.canonical_save_coordinator.dispose()
        self.window._canonical_status_timer.stop()
        self.service.close_project()
        self.window.undo_manager.clear()
        self.window.revision_tracker.reset_for_new_document()
        self.window.close()
        self.window.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        self.temp.cleanup()

    def load_queue(self, path=None):
        if path:
            self.window.queue_mgr.set_srt_for_video(self.item, path)
        with patch("ui.Gui.threading.Thread"):
            self.window.on_queue_item_clicked(self.item)

    def assert_fidelity(self):
        loaded = self.window.sub_editor.all_segments[0]
        for key, value in self.row.items():
            self.assertEqual(loaded[key], value, key)
        self.window.timeline_data_provider.load_runtime_data(self.window.sub_editor.all_segments, 10000)
        self.assertEqual(self.window.timeline_data_provider.get_segment("stable-A").start_ms, 1000)
        self.assertIs(self.window._current_range_segments(), self.window.sub_editor.all_segments)

    def test_real_queue_load_preserves_complete_canonical_payload(self):
        self.load_queue()
        self.assert_fidelity()
        self.window.video_player.sub_controller.load_srt.assert_called_with(self.shadow)

    def test_stale_or_manually_modified_shadow_is_not_canonical_input(self):
        Path(self.shadow).write_text("1\n00:00:05,000 --> 00:00:06,000\nchanged\n", encoding="utf-8")
        self.load_queue()
        self.assert_fidelity()

    def test_workspace_canonical_json_path_does_not_enter_srt_parser(self):
        self.load_queue(self.artifact.path)
        self.assert_fidelity()
        self.window.video_player.sub_controller.load_srt.assert_called_with(self.shadow)

    def test_generated_reload_never_publishes_lossy_rows(self):
        observed = []
        original = self.window.sub_editor.render_page
        def render():
            observed.append(copy.deepcopy(self.window.sub_editor.all_segments))
            original()
        with patch.object(self.window.sub_editor, "render_page", side_effect=render):
            self.window._load_generated_subtitles_into_ui(self.shadow)
        self.assertTrue(observed)
        self.assertTrue(all(rows[0]["id"] == "stable-A" and rows[0].get("words") == self.row["words"] for rows in observed))

    def test_external_srt_remains_an_import(self):
        external = self.root / "external.srt"
        external.write_text("1\n00:00:04,000 --> 00:00:05,000\nimported\n", encoding="utf-8")
        self.load_queue(str(external))
        row = self.window.sub_editor.all_segments[0]
        self.assertNotEqual(row["id"], "stable-A")
        self.assertEqual((row["text"], row["status"]), ("imported", "draft"))

    def test_canonical_hydration_copies_nested_payload(self):
        original = copy.deepcopy(self.row)
        self.window.sub_editor.load_canonical_segments([self.row], self.shadow)
        self.window.sub_editor.all_segments[0]["extra"]["future"].append(3)
        self.assertEqual(self.row, original)

    def test_wrong_artifact_project_is_rejected_without_mutation(self):
        self.load_queue()
        before = copy.deepcopy(self.window.sub_editor.all_segments)
        self.artifact.source_project_id = "another-project"
        with self.assertRaisesRegex(ValueError, "current project"):
            self.window._load_context_subtitles(self.shadow)
        self.assertEqual(self.window.sub_editor.all_segments, before)

    def test_wrong_media_context_is_rejected(self):
        self.load_queue()
        self.window.queue_mgr.active_vid = str(self.root / "other.mp4")
        with self.assertRaisesRegex(ValueError, "media context"):
            self.window._load_context_subtitles(self.shadow)

    def test_corrupt_canonical_artifact_does_not_fall_back_to_shadow(self):
        self.load_queue()
        before = copy.deepcopy(self.window.sub_editor.all_segments)
        Path(self.artifact.path).write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.window._load_context_subtitles(self.shadow)
        self.assertEqual(self.window.sub_editor.all_segments, before)

    def test_workspace_restore_uses_canonical_rows_for_editor_and_shadow_for_player(self):
        self.project.state.active_artifact_id = self.artifact.artifact_id
        with patch("ui.Gui.threading.Thread"), patch("core.services.workspace_service.QTimer.singleShot"):
            self.window.workspace_service.restore_workspace()
        self.assert_fidelity()
        self.window.video_player.sub_controller.load_srt.assert_called_with(self.shadow)

    def test_active_subtitle_artifact_projects_its_own_rows(self):
        self.project.state.subtitle_artifact_id = None
        self.project.state.active_artifact_id = self.artifact.artifact_id
        self.load_queue(self.artifact.path)
        self.assertEqual(self.window.sub_editor.all_segments[0]["id"], "stable-A")
        self.window.video_player.sub_controller.load_srt.assert_called_with(self.shadow)

    def test_switch_a_to_b_to_a_preserves_canonical_payload(self):
        self.service.save_project()
        a_root = self.service.project_dir
        other_media = self.root / "b.mp4"
        other_media.write_bytes(b"B")
        other_project = self.service.create_project(str(self.root / "b.ai-subtitle"), "B", str(other_media))
        other_artifact = self.artifacts.create_artifact_with_data({"version": 1, "segments": [dict(self.row, id="stable-B")]})
        other_shadow = self.window._on_generation_batch_sync()
        other_item = self.window.queue_mgr.ensure_project_binding(str(other_media), project_id=other_project.project_id,
                                                                  project_root=self.service.project_dir)
        self.window.queue_mgr.set_srt_for_video(other_item, other_shadow)
        self.service.save_project()
        self.service.open_project(a_root)
        self.load_queue()
        with patch("ui.Gui.threading.Thread"), patch.object(self.window, "append_log", wraps=self.window.append_log) as logs:
            self.window.on_queue_item_clicked(other_item)
            self.assertIsNotNone(self.service.current_project, logs.call_args_list)
            self.assertEqual(self.window.sub_editor.all_segments[0]["id"], "stable-B",
                             (self.service.current_project.state.subtitle_artifact_id, other_artifact.artifact_id,
                              self.window.queue_mgr.get_active_data()))
            self.window.on_queue_item_clicked(self.item)
        self.assert_fidelity()

    def test_shadow_export_failure_does_not_publish_unbound_runtime(self):
        self.load_queue()
        before = copy.deepcopy(self.window.sub_editor.all_segments)
        with patch.object(self.window, "_on_generation_batch_sync", return_value=None):
            with self.assertRaises(RuntimeError):
                self.window._load_context_subtitles(self.artifact.path)
        self.assertEqual(self.window.sub_editor.all_segments, before)
        self.assertEqual(self.window.sub_editor.srt_path, self.shadow)

    def generate(self, start=3000, end=3500, during_asr=None):
        from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
        from core.subtitle_generation.subtitle_generation_result import SubtitleGenerationResult, WhisperSegmentResult
        from workers.subtitle_generation_worker import SubtitleGenerationWorker
        service = self.window.subtitle_generation_service
        whisper = MagicMock()
        def transcribe(request, batch, cancelled):
            if during_asr:
                during_asr()
            return SubtitleGenerationResult(batch.batch_id, [WhisperSegmentResult(batch.start_ms, batch.end_ms, "new")])
        whisper.transcribe_batch.side_effect = transcribe
        service.whisper_service = whisper
        errors = []
        service.on_error = errors.append
        service.on_finish = self.window._on_interactive_generation_finished
        self.window.generation_panel.video_duration_ms = 10000
        request = SubtitleGenerationRequest("test-range", self.project.project_id, self.project.source.fingerprint,
                                            str(self.media), "tiny", "int8", None, False, 500, True,
                                            range_start_ms=start, range_end_ms=end)
        with patch.object(SubtitleGenerationWorker, "start", lambda worker: worker.run()):
            service.start_generation(request, 10000, existing_segments=self.window.sub_editor.all_segments)
        return whisper, errors

    def test_real_queue_to_generation_preserves_existing_row_and_marks_dirty_once(self):
        self.load_queue()
        before = copy.deepcopy(self.window.sub_editor.all_segments[0])
        with patch.object(self.service, "mark_dirty", wraps=self.service.mark_dirty) as dirty:
            whisper, errors = self.generate()
        self.assertEqual(errors, [])
        self.assertEqual(whisper.transcribe_batch.call_count, 1)
        self.assertEqual(dirty.call_count, 1)
        self.assertEqual(self.window.sub_editor.all_segments[0], before)
        self.assertEqual(len(self.window.sub_editor.all_segments), 2)

    def test_unsaved_trim_after_hydration_allows_generation_without_save(self):
        from core.timeline.timeline_commands import ResizeStartCommand
        self.load_queue()
        self.window.timeline_data_provider.load_runtime_data(self.window.sub_editor.all_segments, 10000)
        self.project.state.active_artifact_id = None
        command = ResizeStartCommand(self.service, self.window.timeline_data_provider, "stable-A", 500)
        self.assertTrue(command.execute())
        self.assertEqual(self.artifacts.load_data(self.artifact.path)["segments"][0]["start_ms"], 1000)
        whisper, errors = self.generate(1000, 1500)
        self.assertEqual(errors, [])
        self.assertEqual(whisper.transcribe_batch.call_count, 1)
        existing = next(row for row in self.window.sub_editor.all_segments if row["id"] == "stable-A")
        self.assertEqual(existing["start_ms"], 1500)
        self.assertEqual(existing["words"], self.row["words"])
        self.assertEqual(existing["extra"], self.row["extra"])

    def test_runtime_change_during_asr_keeps_hydrated_rows_and_rejects_commit(self):
        self.load_queue()
        def edit():
            self.window.sub_editor.all_segments[0]["end_ms"] = 3200
        whisper, errors = self.generate(during_asr=edit)
        self.assertEqual(whisper.transcribe_batch.call_count, 1)
        self.assertTrue(any(error.startswith("STALE_RANGE_CONFLICT:") for error in errors))
        self.assertEqual(len(self.window.sub_editor.all_segments), 1)
        self.assertEqual(self.window.sub_editor.all_segments[0]["id"], "stable-A")
        self.assertEqual(self.window.sub_editor.all_segments[0]["words"], self.row["words"])

    def test_generation_error_keeps_hydrated_rows_unchanged(self):
        self.load_queue()
        before = copy.deepcopy(self.window.sub_editor.all_segments)
        def fail():
            raise RuntimeError("ASR failed")
        _whisper, errors = self.generate(during_asr=fail)
        self.assertTrue(errors)
        self.assertEqual(self.window.sub_editor.all_segments, before)


if __name__ == "__main__":
    unittest.main()
