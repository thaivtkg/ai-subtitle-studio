import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.Gui import MainWindow
from core.recovery.recovery_models import RecoveryWorkingState


class TestLinkedRecoveryRestore(unittest.TestCase):
    def _window(self, canonical_text="Canonical"):
        window = MainWindow.__new__(MainWindow)
        events = []

        project = SimpleNamespace(
            source=SimpleNamespace(path="D:/video.mp4"),
            state=SimpleNamespace(workspace=SimpleNamespace()),
            transcription_context=SimpleNamespace(),
        )

        project_service = SimpleNamespace(current_project=None, project_dir=None)

        def open_project(path):
            events.append("open_project")
            project_service.current_project = project
            project_service.project_dir = path
            return project

        project_service.open_project = MagicMock(side_effect=open_project)
        window.project_service = project_service

        def apply_workspace(workspace_state):
            events.append("restore_workspace")
            window.sub_editor.all_segments = [
                {"stt": "1", "start": 0, "end": 2000, "text": canonical_text}
            ]
            window.queue_mgr.active_vid = "D:/video.mp4"

        window.workspace_service = SimpleNamespace(
            apply_workspace=MagicMock(side_effect=apply_workspace)
        )
        window.sub_editor = SimpleNamespace(
            all_segments=[],
            render_page=MagicMock(side_effect=lambda: events.append("render_editor")),
        )
        window.timeline_data_provider = SimpleNamespace(
            load_runtime_data=MagicMock(),
            get_all_segments=MagicMock(return_value=[]),
        )
        window.timeline_widget = SimpleNamespace(load_project_data=MagicMock())
        window.video_player = SimpleNamespace(
            get_video_duration_ms=MagicMock(return_value=120000),
            load_video=MagicMock(),
        )
        window.queue_mgr = SimpleNamespace(active_vid=None)
        window.global_undo_manager = SimpleNamespace(clear=MagicMock())
        window.recovery_manager = SimpleNamespace(_active_session=None)
        window.revision_tracker = SimpleNamespace(restore_from_snapshot=MagicMock())
        window._update_window_title_dirty_marker = MagicMock()
        window._refresh_transcription_context_views = MagicMock()
        window._recovery_test_events = events
        return window

    def _state(self, text="Recovered"):
        return RecoveryWorkingState(
            schema_version=2.0,
            session_id="recovery-1",
            project_id="project-1",
            project_file_path="D:/project.ai-subtitle",
            video_path="D:/video.mp4",
            source_fingerprint="fingerprint",
            edit_revision=7,
            segments=[
                {"stt": "1", "start": 0, "end": 2000, "text": text}
            ],
            workspace_state={
                "active_page": "workspace",
                "active_tab": "inline_editor",
                "playback_position_ms": 63220,
                "subtitle_preview_enabled": True,
            },
        )

    def test_linked_recovery_reopens_project_and_restores_context_before_segments(self):
        window = self._window()

        window.apply_recovery_working_state(self._state(), linked=True)

        window.project_service.open_project.assert_called_once_with(
            "D:/project.ai-subtitle"
        )
        window.workspace_service.apply_workspace.assert_called_once()
        self.assertEqual(window._recovery_test_events[:2], ["open_project", "restore_workspace"])
        self.assertEqual(window.sub_editor.all_segments[0]["text"], "Recovered")

    def test_recovered_segments_win_over_canonical_artifact(self):
        window = self._window(canonical_text="Saved artifact")

        window.apply_recovery_working_state(self._state("Unsaved recovery"), linked=True)

        self.assertEqual(window.sub_editor.all_segments[0]["text"], "Unsaved recovery")

    def test_linked_recovery_restores_queue_video_position_and_duration(self):
        window = self._window()

        window.apply_recovery_working_state(self._state(), linked=True)

        restored_workspace = window.workspace_service.apply_workspace.call_args.args[0]
        self.assertEqual(restored_workspace["playback_position_ms"], 63220)
        self.assertEqual(window.queue_mgr.active_vid, "D:/video.mp4")
        window.video_player.load_video.assert_not_called()
        window.timeline_data_provider.load_runtime_data.assert_called_once()
        self.assertEqual(
            window.timeline_data_provider.load_runtime_data.call_args.args[1],
            120000,
        )
        self.assertEqual(
            window.timeline_widget.load_project_data.call_args.args[0],
            120000,
        )
        self.assertEqual(
            window.video_player.get_video_duration_ms.call_count,
            1,
        )

    def test_unlinked_recovery_keeps_segments_without_project_or_video_restore(self):
        window = self._window()

        window.apply_recovery_working_state(self._state(), linked=False)

        window.project_service.open_project.assert_not_called()
        window.workspace_service.apply_workspace.assert_not_called()
        window.video_player.load_video.assert_not_called()
        self.assertEqual(window.sub_editor.all_segments[0]["text"], "Recovered")


if __name__ == "__main__":
    unittest.main()
