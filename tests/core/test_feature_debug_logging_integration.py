import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.artifacts.artifact_store import ArtifactStore
from core.artifacts.artifact_types import ArtifactType
from core.debug_logging import DebugConfig
from core.services.project_service import ProjectService
from ui.Gui import MainWindow


class DebugLoggingProductionIntegrationContracts(unittest.TestCase):
    CATEGORIES = (
        "recovery",
        "canonical_save",
        "project_switch",
        "project_status",
        "waveform",
        "artifact_sync",
    )

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        self._temp_dir = tempfile.TemporaryDirectory()
        root = Path(self._temp_dir.name)
        self._patchers = [
            patch(
                "ui.Gui.RuntimePaths.get_recovery_sessions_dir",
                return_value=root / "sessions",
            ),
            patch(
                "ui.Gui.RuntimePaths.get_recovery_quarantine_dir",
                return_value=root / "quarantine",
            ),
            patch(
                "ui.Gui.RuntimePaths.get_tutorial_progress_file",
                return_value=root / "tutorial_progress.json",
            ),
            patch("ui.Gui.load_settings", return_value={}),
            patch("ui.Gui.save_settings"),
            patch(
                "ui.subtitle_generation_panel.SubtitleGenerationPanel.check_resumable_state"
            ),
        ]
        for patcher in self._patchers:
            patcher.start()
        self._windows = []
        self.addCleanup(self._cleanup_windows)

    def _cleanup_windows(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        for window in reversed(self._windows):
            window.close()
            window.deleteLater()
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._temp_dir.cleanup()

    def _window(self, project_service=None):
        service = project_service or MagicMock()
        service.current_project = getattr(service, "current_project", None)
        service.project_dir = getattr(service, "project_dir", None)
        window = MainWindow(
            project_service=service,
            media_import_service=MagicMock(),
        )
        self._windows.append(window)
        self.app.processEvents()
        return window

    def _require_debug_runtime(self, window):
        config = getattr(window, "_debug_config", None)
        self.assertIsInstance(
            config,
            DebugConfig,
            "MainWindow must own the session DebugConfig at _debug_config",
        )
        emitter = getattr(window, "_emit_debug_event", None)
        self.assertTrue(
            callable(emitter),
            "MainWindow must expose the central _emit_debug_event seam",
        )
        return config, emitter

    def _run_category_operation_pair(self, category, operation, snapshot):
        outcomes = []
        for enabled in (False, True):
            window = self._window()
            config = DebugConfig(
                master_enabled=True,
                enabled_categories={category} if enabled else set(),
            )
            window._debug_config = config
            emitter = getattr(window, "_emit_debug_event", None)
            if not callable(emitter):
                operation(window)
                self.assertTrue(
                    callable(emitter),
                    "operation must route diagnostics through _emit_debug_event",
                )
                return
            boundary = MagicMock(wraps=emitter)
            with patch.object(window, "_emit_debug_event", boundary):
                outcome = operation(window)
            category_calls = [
                call
                for call in boundary.call_args_list
                if call.args and call.args[0] == category
            ]
            self.assertEqual(
                len(category_calls),
                1,
                f"{category} operation must emit one semantic boundary event",
            )
            outcomes.append(snapshot(outcome, window))
        self.assertEqual(outcomes[0], outcomes[1])

    def test_INT01_mainwindow_owns_session_debug_config(self):
        window = self._window()
        config = getattr(window, "_debug_config", None)

        self.assertIsInstance(config, DebugConfig)
        self.assertFalse(config.master_enabled)
        self.assertEqual(config.enabled_categories, set())

        for category in self.CATEGORIES:
            self.assertNotIn(category, config.enabled_categories)

    def test_INT02_central_emission_gate_blocks_before_activity_sink(self):
        window = self._window()
        config, emit = self._require_debug_runtime(window)
        sink = MagicMock()

        with patch.object(window, "append_log", sink):
            config.master_enabled = False
            config.enabled_categories = {"recovery"}
            emit("recovery", "probe")
            self.assertEqual(sink.call_count, 0)

            config.master_enabled = True
            config.enabled_categories = set()
            emit("recovery", "probe")
            self.assertEqual(sink.call_count, 0)

            config.enabled_categories = {"recovery"}
            emit("recovery", "probe")
            self.assertEqual(sink.call_count, 1)

    def test_INT03_recovery_switch_emits_without_changing_session_result(self):
        def operation(window):
            window.project_service.current_project = None
            window.project_service.current_project_id = "project-a"
            window.project_service.current_project_path = "project-a.ai-subtitle"
            session = window._switch_recovery_session()
            return (
                session.manifest.project_id,
                session.manifest.project_file_path,
            )

        self._run_category_operation_pair(
            "recovery",
            operation,
            lambda result, _window: result,
        )

    def test_INT04_canonical_save_emits_without_changing_save_result(self):
        def operation(window):
            root = Path(self._temp_dir.name) / "canonical-save"
            video = root / "video.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b"video")
            service = ProjectService()
            service.create_project(str(root / "project.ai-subtitle"), "Project", str(video))
            window.project_service = service
            window.artifact_store = service.artifact_store
            window.workspace_service.capture_workspace = MagicMock(return_value={})
            result = window._save_current_project(notify_user=False)
            return result, service.current_project.state.dirty

        self._run_category_operation_pair(
            "canonical_save",
            operation,
            lambda result, _window: result,
        )

    def test_INT05_project_switch_emits_without_changing_project_identity(self):
        def operation(window):
            root = Path(self._temp_dir.name) / "project-switch"
            video = root / "shared.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b"video")
            service = ProjectService()
            project_a = service.create_project(str(root / "A.ai-subtitle"), "A", str(video))
            project_b = service.create_project(str(root / "B.ai-subtitle"), "B", str(video))
            service.open_project(str(root / "B.ai-subtitle"))
            window.project_service = service
            window.artifact_store = service.artifact_store
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window._sync_subtitle_placement_from_project = MagicMock()
            window._prepare_recovery_session_switch = MagicMock(return_value=True)
            window._complete_recovery_session_switch = MagicMock()
            item = window.queue_mgr.ensure_project_binding(
                str(video), project_id=project_a.project_id, project_root=str(root / "A.ai-subtitle")
            )
            window.queue_mgr.set_active(
                window.queue_mgr.ensure_project_binding(
                    str(video), project_id=project_b.project_id, project_root=str(root / "B.ai-subtitle")
                )
            )
            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(item)
            current_project = service.current_project
            return {
                "target_name": current_project.name,
                "target_root": Path(service.project_dir).name,
                "target_selected": current_project.project_id == project_a.project_id,
                "source_replaced": current_project.project_id != project_b.project_id,
            }

        self._run_category_operation_pair(
            "project_switch",
            operation,
            lambda result, _window: result,
        )

    def test_INT06_project_status_emits_only_for_meaningful_transition(self):
        outcomes = []
        for enabled in (False, True):
            window = self._window()
            config = DebugConfig(
                master_enabled=True,
                enabled_categories={"project_status"} if enabled else set(),
            )
            window._debug_config = config
            emitter = getattr(window, "_emit_debug_event", None)
            if not callable(emitter):
                window._update_window_title_dirty_marker(False)
                window._update_window_title_dirty_marker(True)
                window._update_window_title_dirty_marker(True)
                self.assertTrue(
                    callable(emitter),
                    "status transitions must route through _emit_debug_event",
                )
                return

            boundary = MagicMock(wraps=emitter)
            with patch.object(window, "_emit_debug_event", boundary):
                window._update_window_title_dirty_marker(False)
                window._update_window_title_dirty_marker(True)
                title_after_transition = window.windowTitle()
                window._update_window_title_dirty_marker(True)

            calls = [
                call
                for call in boundary.call_args_list
                if call.args and call.args[0] == "project_status"
            ]
            self.assertEqual(len(calls), 1)
            self.assertEqual(window.windowTitle(), title_after_transition)
            outcomes.append(window.windowTitle())
        self.assertEqual(outcomes[0], outcomes[1])

    def test_INT07_waveform_completion_slot_emits_on_gui_thread_without_worker_call(self):
        def operation(window):
            window.queue_mgr.active_vid = "video.mp4"
            window.generation_panel.set_video_duration = MagicMock()
            window.timeline_data_provider.load_runtime_data = MagicMock()
            window.timeline_data_provider.get_all_segments = MagicMock(return_value=[])
            window.timeline_widget.load_project_data = MagicMock()
            window.sub_editor.all_segments = []
            window._on_waveform_ready_slot("video.mp4", 1000, [])
            return (
                window.generation_panel.set_video_duration.call_args.args,
                window.timeline_widget.load_project_data.call_args.args,
            )

        self._run_category_operation_pair(
            "waveform",
            operation,
            lambda result, _window: result,
        )

    def test_INT08_artifact_registration_emits_without_changing_artifact_state(self):
        def operation(window):
            root = Path(self._temp_dir.name) / "artifact-sync"
            root.mkdir(parents=True, exist_ok=True)
            artifact_path = root / "timing.srt"
            artifact_path.write_text("1\n00:00:00,000 --> 00:00:01,000\ntext\n", encoding="utf-8")
            project = SimpleNamespace(
                project_id="project-a",
                state=SimpleNamespace(
                    active_artifact_id=None,
                    timing_status="EMPTY",
                    text_status="EMPTY",
                    timing=None,
                ),
            )
            service = MagicMock()
            service.current_project = project
            service.mark_dirty = MagicMock()
            window.project_service = service
            window.artifact_store = ArtifactStore()
            count_before = len(window.artifact_store.get_all())
            artifact = window._register_artifact(
                str(artifact_path), ArtifactType.TIMING, mark_dirty=True
            )
            return {
                "registered": artifact is not None,
                "count_delta": len(window.artifact_store.get_all()) - count_before,
                "kind": artifact.artifact_type.name if artifact else None,
                "path_name": Path(artifact.path).name if artifact else None,
                "timing_status": project.state.timing_status,
            }

        self._run_category_operation_pair(
            "artifact_sync",
            operation,
            lambda result, _window: result,
        )

    def test_INT09_production_category_isolation(self):
        window = self._window()
        config = DebugConfig(master_enabled=True, enabled_categories={"waveform"})
        window._debug_config = config
        emitter = getattr(window, "_emit_debug_event", None)

        def run_operations():
            root = Path(self._temp_dir.name) / "category-isolation"
            video = root / "video.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b"video")
            service = ProjectService()
            service.create_project(str(root / "project.ai-subtitle"), "Project", str(video))
            window.project_service = service
            window.artifact_store = service.artifact_store
            window.workspace_service.capture_workspace = MagicMock(return_value={})
            window._save_current_project(notify_user=False)

            window.queue_mgr.active_vid = "video.mp4"
            window.generation_panel.set_video_duration = MagicMock()
            window.timeline_data_provider.load_runtime_data = MagicMock()
            window.timeline_data_provider.get_all_segments = MagicMock(return_value=[])
            window.timeline_widget.load_project_data = MagicMock()
            window.sub_editor.all_segments = []
            window._on_waveform_ready_slot("video.mp4", 1000, [])

        if not callable(emitter):
            self.assertTrue(callable(emitter))
            return

        downstream = MagicMock()
        with patch.object(window, "append_log", downstream):
            run_operations()

        debug_messages = [
            call.args[0]
            for call in downstream.call_args_list
            if call.args
            and isinstance(call.args[0], str)
            and call.args[0].startswith("[DEBUG][")
        ]
        canonical_save_messages = [
            message
            for message in debug_messages
            if message.startswith("[DEBUG][canonical_save]")
        ]
        waveform_messages = [
            message
            for message in debug_messages
            if message.startswith("[DEBUG][waveform]")
        ]
        self.assertEqual(canonical_save_messages, [])
        self.assertEqual(len(waveform_messages), 1)

    def test_INT10_waveform_diagnostics_follow_debug_gate(self):
        window = self._window()
        window.queue_mgr.active_vid = "video.mp4"
        window.generation_panel.set_video_duration = MagicMock()
        window.timeline_data_provider.load_runtime_data = MagicMock()
        window.timeline_data_provider.get_all_segments = MagicMock(return_value=[])
        window.timeline_widget.load_project_data = MagicMock()
        window.sub_editor.all_segments = []

        signal = getattr(window, "waveform_debug_signal", None)
        self.assertIsNotNone(signal, "worker diagnostics must return through a Qt signal")

        window._debug_config = DebugConfig()
        start_index = len(window.page_dashboard.activity_log_model.entries)
        signal.emit("waveform load started: video.mp4")
        window._on_waveform_ready_slot("video.mp4", 1000, [])
        self.app.processEvents()
        disabled_entries = window.page_dashboard.activity_log_model.entries[start_index:]
        self.assertEqual(
            [entry for entry in disabled_entries if entry.level == "DEBUG"],
            [],
        )

        window._debug_config = DebugConfig(
            master_enabled=True,
            enabled_categories={"waveform"},
        )
        start_index = len(window.page_dashboard.activity_log_model.entries)
        signal.emit("waveform load started: video.mp4")
        window._on_waveform_ready_slot("video.mp4", 1000, [])
        self.app.processEvents()
        enabled_debug_messages = [
            entry.message
            for entry in window.page_dashboard.activity_log_model.entries[start_index:]
            if entry.level == "DEBUG" and entry.message.startswith("[waveform]")
        ]
        self.assertEqual(
            enabled_debug_messages,
            [
                "[waveform] waveform load started: video.mp4",
                "[waveform] waveform accepted",
            ],
        )

    def test_INT11_waveform_errors_remain_visible_when_debug_is_off(self):
        window = self._window()
        window._debug_config = DebugConfig()
        window.queue_mgr.active_vid = "video.mp4"
        window.generation_panel.set_video_duration = MagicMock()
        window.timeline_data_provider.load_runtime_data = MagicMock()
        window.timeline_data_provider.get_all_segments = MagicMock(return_value=[])
        window.timeline_widget.load_project_data = MagicMock(
            side_effect=RuntimeError("timeline failed")
        )
        window.sub_editor.all_segments = []

        start_index = len(window.page_dashboard.activity_log_model.entries)
        window._on_waveform_ready_slot("video.mp4", 1000, [])
        self.app.processEvents()
        new_entries = window.page_dashboard.activity_log_model.entries[start_index:]

        self.assertEqual(
            [entry.raw_text for entry in new_entries if entry.level == "ERROR"],
            ["[ERROR-WAVEFORM] Timeline rendering failed: timeline failed"],
        )
        self.assertEqual(
            [entry for entry in new_entries if entry.level == "DEBUG"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
