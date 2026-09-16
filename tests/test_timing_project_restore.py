import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from core.artifacts.artifact_store import ArtifactStore
from core.project.project_state import TimingState
from core.services.project_service import ProjectService
from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_placement import SubtitlePlacementState
from core.timing.timing_batch_service import TimingBatchService
from core.timing.timing_checkpoint import TimingCheckpoint
from ui.subtitle_generation_panel import SubtitleGenerationPanel


class TestTimingProjectRestore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _project(self):
        root = tempfile.mkdtemp()
        video_path = os.path.join(root, "video.mp4")
        with open(video_path, "wb") as handle:
            handle.write(b"video")
        project_dir = os.path.join(root, "project.ai-subtitle")
        service = ProjectService(ArtifactStore())
        service.create_project(project_dir, "video.mp4", video_path)
        return root, project_dir, service

    @staticmethod
    def _panel(service):
        return SubtitleGenerationPanel(
            SubtitleGenerationService(FasterWhisperService(), service)
        )

    @staticmethod
    def _configure_timing(panel):
        panel.cmb_mode.setCurrentIndex(1)
        panel.cmb_model.setCurrentText("large-v3-turbo")
        panel.cmb_compute.setCurrentText("float16")
        panel.chk_fix_overlap.setChecked(True)
        panel.spin_overlap_gap.setValue(80)

    @staticmethod
    def _commit_finished_batch(service, task_mode="timing"):
        state = service.current_project.state
        state.task_mode = task_mode
        state.timing = TimingState(
            model_size="small",
            compute_type="int8",
            use_vad=True,
            min_silence_ms=731,
            fix_overlap=True,
            overlap_gap_ms=137,
            overlap_ms=913,
            max_window_ms=98765,
            batch_size=2,
            next_segment_index=1,
        )
        service.save_project()

        timing_service = TimingBatchService(service)
        timing_service._current_settings = {
            "model_size": "small",
            "compute_type": "int8",
            "use_vad": True,
            "min_silence_ms": 731,
            "fix_overlap": True,
            "overlap_gap_ms": 137,
            "overlap_ms": 913,
            "max_window_ms": 98765,
        }
        timing_service._on_worker_finished(
            [
                {"start_ms": 1000, "end_ms": 2000, "text": "A"},
                {"start_ms": 3000, "end_ms": 4000, "text": "B"},
            ],
            True,
        )
        return timing_service

    def test_r1_timing_transaction_preserves_task_mode(self):
        root, project_dir, service = self._project()
        try:
            self._commit_finished_batch(service)
            with open(os.path.join(project_dir, "state.json"), encoding="utf-8") as handle:
                disk_state = json.load(handle)
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            self.assertEqual(disk_state["task_mode"], "timing")
            self.assertEqual(reopened.current_project.state.task_mode, "timing")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_r2_timing_transaction_preserves_unrelated_project_state(self):
        root, project_dir, service = self._project()
        try:
            state = service.current_project.state
            state.task_mode = "timing"
            state.text_status = "READY"
            state.export_status = "DONE"
            state.subtitle_artifact_id = "subtitle-artifact"
            state.selected_segment_id = "segment-7"
            state.subtitle_placement = SubtitlePlacementState(mode="top", x=0.2, y=0.3)
            self._commit_finished_batch(service)

            with open(os.path.join(project_dir, "state.json"), encoding="utf-8") as handle:
                disk_state = json.load(handle)
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            restored = reopened.current_project.state
            self.assertEqual(disk_state["text_status"], "READY")
            self.assertEqual(disk_state["export_status"], "DONE")
            self.assertEqual(
                disk_state["active_artifact_id"],
                restored.timing.timing_artifact_id,
            )
            self.assertEqual(disk_state["subtitle_artifact_id"], "subtitle-artifact")
            self.assertEqual(disk_state["selected_segment_id"], "segment-7")
            self.assertEqual(disk_state["subtitle_placement"], {"mode": "top", "x": 0.2, "y": 0.3})
            self.assertEqual(restored.text_status, "READY")
            self.assertEqual(restored.export_status, "DONE")
            self.assertEqual(restored.subtitle_artifact_id, "subtitle-artifact")
            self.assertEqual(restored.selected_segment_id, "segment-7")
            self.assertEqual(restored.subtitle_placement, SubtitlePlacementState(mode="top", x=0.2, y=0.3))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_r3_worker_finished_commit_round_trips_timing_artifact(self):
        root, project_dir, service = self._project()
        try:
            self._commit_finished_batch(service)
            expected = service.current_project.state
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            restored = reopened.current_project.state
            self.assertEqual(restored.task_mode, "timing")
            self.assertEqual(restored.timing.model_size, "small")
            self.assertEqual(restored.timing.compute_type, "int8")
            self.assertEqual(restored.timing.overlap_gap_ms, 137)
            self.assertEqual(restored.timing.timing_artifact_id, expected.timing.timing_artifact_id)
            self.assertEqual(restored.timing_status, "READY")
            self.assertTrue(os.path.exists(
                reopened.artifact_store.get(restored.timing.timing_artifact_id).path
            ))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_r4_timing_transaction_preserves_asr_task_mode(self):
        root, project_dir, service = self._project()
        try:
            self._commit_finished_batch(service, task_mode="asr")
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            self.assertEqual(reopened.current_project.state.task_mode, "asr")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_r5_retry_uses_checkpoint_owned_settings(self):
        root, _project_dir, service = self._project()
        try:
            project = service.current_project
            checkpoint_settings = {
                "model_size": "large-v3-turbo",
                "compute_type": "float16",
                "use_vad": True,
                "min_silence_ms": 500,
                "fix_overlap": True,
                "overlap_gap_ms": 80,
                "overlap_ms": 800,
                "max_window_ms": 120000,
            }
            caller_settings = {
                "model_size": "small",
                "compute_type": "int8",
                "use_vad": True,
                "min_silence_ms": 900,
                "fix_overlap": False,
                "overlap_gap_ms": 137,
                "overlap_ms": 1200,
                "max_window_ms": 60000,
            }
            service.save_timing_checkpoint(TimingCheckpoint(
                project_id=project.project_id,
                source_fingerprint=project.source.fingerprint,
                timing_artifact_id="",
                timing_revision=1,
                batch_size=1,
                active_batch={
                    "start_segment": 1,
                    "start_ms": 250,
                    "status": "FAILED",
                },
                **checkpoint_settings,
            ))
            timing_service = TimingBatchService(service)
            captured = []
            timing_service._execute_run = lambda **kwargs: captured.append(kwargs)

            timing_service.retry_timing(3, caller_settings)

            self.assertEqual(captured[0]["target_count"], 3)
            self.assertEqual(captured[0]["settings"], checkpoint_settings)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_r6_resume_transaction_preserves_current_project_preference(self):
        root, project_dir, service = self._project()
        try:
            checkpoint_settings = {
                "model_size": "large-v3-turbo",
                "compute_type": "float16",
                "use_vad": True,
                "min_silence_ms": 500,
                "fix_overlap": True,
                "overlap_gap_ms": 80,
                "overlap_ms": 800,
                "max_window_ms": 120000,
            }
            current_settings = {
                "model_size": "small",
                "compute_type": "int8",
                "use_vad": True,
                "min_silence_ms": 500,
                "fix_overlap": False,
                "overlap_gap_ms": 137,
                "overlap_ms": 800,
                "max_window_ms": 120000,
            }
            state = service.current_project.state
            state.task_mode = "timing"
            for name, value in checkpoint_settings.items():
                setattr(state.timing, name, value)
            state.timing.batch_size = 1
            state.timing.next_segment_index = 1
            service.save_project()

            timing_service = TimingBatchService(service)
            timing_service._current_settings = checkpoint_settings.copy()
            timing_service._on_worker_finished(
                [{"start_ms": 1000, "end_ms": 2000}], True
            )

            for name, value in current_settings.items():
                setattr(state.timing, name, value)
            captured = []
            timing_service._execute_run = lambda **kwargs: captured.append(kwargs)
            timing_service.continue_timing(1, current_settings)
            self.assertEqual(captured[0]["settings"], checkpoint_settings)

            timing_service._current_settings = checkpoint_settings.copy()
            timing_service._on_worker_finished(
                [{"start_ms": 3000, "end_ms": 4000}], True
            )

            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            restored_timing = reopened.current_project.state.timing
            checkpoint = reopened.load_timing_checkpoint()
            self.assertEqual(restored_timing.model_size, "small")
            self.assertEqual(restored_timing.compute_type, "int8")
            self.assertFalse(restored_timing.fix_overlap)
            self.assertEqual(restored_timing.overlap_gap_ms, 137)
            self.assertEqual(checkpoint.model_size, "large-v3-turbo")
            self.assertEqual(checkpoint.compute_type, "float16")
            self.assertTrue(checkpoint.fix_overlap)
            self.assertEqual(checkpoint.overlap_gap_ms, 80)
            self.assertEqual(reopened.current_project.state.task_mode, "timing")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p1_real_ui_mutation_save_and_reload(self):
        root, project_dir, service = self._project()
        try:
            panel = self._panel(service)
            self._configure_timing(panel)
            service.save_project()

            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            timing = reopened.current_project.state.timing
            self.assertEqual(timing.model_size, "large-v3-turbo")
            self.assertEqual(timing.compute_type, "float16")
            self.assertTrue(timing.fix_overlap)
            self.assertEqual(timing.overlap_gap_ms, 80)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p2_loaded_timing_project_restores_panel_mode_and_values(self):
        root, project_dir, service = self._project()
        try:
            panel = self._panel(service)
            self._configure_timing(panel)
            service.save_project()

            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            restored_panel = self._panel(reopened)
            restored_panel.sync_timing_settings_from_project()

            self.assertEqual(restored_panel.cmb_mode.currentData(), "timing")
            self.assertEqual(restored_panel.cmb_model.currentText(), "large-v3-turbo")
            self.assertEqual(restored_panel.cmb_compute.currentText(), "float16")
            self.assertTrue(restored_panel.chk_fix_overlap.isChecked())
            self.assertEqual(restored_panel.spin_overlap_gap.value(), 80)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p3_round_trip_preserves_all_timing_values(self):
        root, project_dir, service = self._project()
        try:
            service.current_project.state.timing = TimingState(
                model_size="small",
                compute_type="int8",
                use_vad=True,
                min_silence_ms=731,
                fix_overlap=True,
                overlap_gap_ms=137,
                overlap_ms=913,
                max_window_ms=98765,
            )
            service.save_project()
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            self.assertEqual(reopened.current_project.state.timing, service.current_project.state.timing)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p4_round_trip_preserves_false_overlap_and_custom_gap(self):
        root, project_dir, service = self._project()
        try:
            service.current_project.state.timing.fix_overlap = False
            service.current_project.state.timing.overlap_gap_ms = 137
            service.save_project()
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            timing = reopened.current_project.state.timing
            self.assertFalse(timing.fix_overlap)
            self.assertEqual(timing.overlap_gap_ms, 137)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p5_programmatic_panel_restore_does_not_dirty(self):
        root, project_dir, service = self._project()
        try:
            service.current_project.state.task_mode = "timing"
            service.current_project.state.timing.overlap_gap_ms = 80
            service.save_project()
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            reopened.revision_tracker = MagicMock(is_transitioning=False)
            panel = self._panel(reopened)
            panel.sync_timing_settings_from_project()
            self.assertFalse(reopened.current_project.state.dirty)
            reopened.revision_tracker.record_external_change.assert_not_called()
            panel.spin_overlap_gap.setValue(81)
            reopened.revision_tracker.record_external_change.assert_called_once_with()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p6_mode_switch_keeps_timing_preferences(self):
        root, _project_dir, service = self._project()
        try:
            panel = self._panel(service)
            self._configure_timing(panel)
            panel.cmb_mode.setCurrentIndex(0)
            panel.cmb_mode.setCurrentIndex(1)
            self.assertEqual(panel.cmb_model.currentText(), "large-v3-turbo")
            self.assertEqual(panel.cmb_compute.currentText(), "float16")
            self.assertEqual(panel.spin_overlap_gap.value(), 80)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p7_project_switch_keeps_timing_settings_isolated(self):
        root, project_a, service = self._project()
        video_b = os.path.join(root, "video-b.mp4")
        with open(video_b, "wb") as handle:
            handle.write(b"video-b")
        project_b = os.path.join(root, "project-b.ai-subtitle")
        try:
            service.current_project.state.timing.overlap_gap_ms = 80
            service.save_project()
            service.create_project(project_b, "video-b.mp4", video_b)
            service.current_project.state.timing.overlap_gap_ms = 137
            service.save_project()
            service.open_project(project_a)
            self.assertEqual(service.current_project.state.timing.overlap_gap_ms, 80)
            service.open_project(project_b)
            self.assertEqual(service.current_project.state.timing.overlap_gap_ms, 137)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p8_legacy_project_without_timing_loads_cleanly(self):
        root, project_dir, service = self._project()
        try:
            service.save_project()
            state_path = os.path.join(project_dir, "state.json")
            with open(state_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.pop("timing", None)
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            reopened = ProjectService(ArtifactStore())
            reopened.open_project(project_dir)
            self.assertEqual(reopened.current_project.state.timing, TimingState())
            self.assertFalse(reopened.current_project.state.dirty)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p9_legacy_project_without_task_mode_defaults_without_mutation(self):
        root, project_dir, service = self._project()
        try:
            service.save_project()
            state_path = os.path.join(project_dir, "state.json")
            with open(state_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.pop("task_mode", None)
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)

            reopened = ProjectService(ArtifactStore())
            reopened.revision_tracker = MagicMock(is_transitioning=False)
            reopened.open_project(project_dir)

            self.assertEqual(reopened.current_project.state.task_mode, "asr")
            self.assertFalse(reopened.current_project.state.dirty)
            reopened.revision_tracker.record_external_change.assert_not_called()
            with open(state_path, "r", encoding="utf-8") as handle:
                self.assertNotIn("task_mode", json.load(handle))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _corrupt_timing_vad_fixture(self):
        root, project_dir, service = self._project()
        service.current_project.state.task_mode = "timing"
        service.current_project.state.timing.use_vad = False
        service.save_project()
        reopened = ProjectService(ArtifactStore())
        reopened.open_project(project_dir)
        return root, reopened

    def test_p10_timing_restore_forces_vad_in_ui_and_effective_settings(self):
        root, service = self._corrupt_timing_vad_fixture()
        try:
            panel = self._panel(service)
            panel.sync_timing_settings_from_project()
            self.assertTrue(panel.chk_vad.isChecked())
            self.assertTrue(panel._timing_settings()["use_vad"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p10_timing_generate_forces_vad_true(self):
        root, service = self._corrupt_timing_vad_fixture()
        try:
            panel = self._panel(service)
            panel.sync_timing_settings_from_project()
            panel.video_duration_ms = 1
            panel._set_ui_state_running = lambda: None
            panel._has_resumable_timing_checkpoint = lambda: False
            calls = []
            panel.timing_start_requested.connect(lambda _batch, settings: calls.append(settings))
            panel._on_generate_clicked()
            self.assertTrue(calls[0]["use_vad"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_p10_timing_resume_forces_vad_true(self):
        root, service = self._corrupt_timing_vad_fixture()
        try:
            panel = self._panel(service)
            panel.sync_timing_settings_from_project()
            panel._set_ui_state_running = lambda: None
            calls = []
            panel.timing_resume_requested.connect(lambda _batch, settings: calls.append(settings))
            panel._on_resume_clicked()
            self.assertTrue(calls[0]["use_vad"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
