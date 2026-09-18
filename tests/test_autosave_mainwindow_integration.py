import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.recovery.recovery_models import RecoveryContext, RecoveryManifest, RecoverySession
from core.recovery.autosave_coordinator import AutosaveCoordinator
from ui.Gui import MainWindow


class _Scheduler:
    def __init__(self):
        self.now = 0
        self._next = 0
        self._events = {}

    def call_later(self, delay_ms, callback):
        self._next += 1
        self._events[self._next] = (self.now + delay_ms, callback)
        return self._next

    def cancel(self, handle):
        self._events.pop(handle, None)

    def advance(self, elapsed_ms):
        target = self.now + elapsed_ms
        while True:
            due = [
                (deadline, handle, callback)
                for handle, (deadline, callback) in self._events.items()
                if deadline <= target
            ]
            if not due:
                self.now = target
                return
            deadline, handle, callback = min(due)
            self.now = deadline
            self._events.pop(handle, None)
            callback()


@dataclass
class _SessionStore:
    root: Path

    def __post_init__(self):
        self._active_session = None
        self.created_contexts = []
        self.snapshots = []

    def create_session(self, context):
        self.created_contexts.append(context)
        session_id = context.session_id or f"session-{context.project_id}"
        directory = self.root / session_id
        directory.mkdir(parents=True, exist_ok=True)
        manifest = RecoveryManifest(
            schema_version=1,
            session_id=session_id,
            app_version=context.app_version,
            project_id=context.project_id,
            project_file_path=context.project_file_path,
            video_path=context.video_path,
            source_fingerprint=context.source_fingerprint,
            source_modified_at=context.source_modified_at,
            created_at="now",
            last_snapshot_at=None,
            edit_revision=0,
            snapshot_revision=0,
            last_saved_revision=0,
            last_clean_revision=0,
        )
        self._active_session = RecoverySession(session_id, directory, manifest)
        return self._active_session

    def finalize_clean_shutdown(self):
        return False


class TestAutosaveMainWindowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.project_service = MagicMock()
        with patch(
            "ui.subtitle_generation_panel.SubtitleGenerationPanel.check_resumable_state"
        ):
            self.window = MainWindow(
                project_service=self.project_service,
                media_import_service=MagicMock(),
            )
        self.addCleanup(self.window.close)
        self.addCleanup(self.window.revision_tracker.reset_for_new_document)

        self.window.autosave_coordinator.dispose()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.session_store = _SessionStore(Path(self.temp_dir.name))
        self.session_store._active_session = self.session_store.create_session(
            RecoveryContext(
                "project-a",
                str(Path(self.temp_dir.name) / "project-a.ai-subtitle"),
                "video-a.mp4",
                "fp-a",
                0.0,
                session_id="session-a",
            )
        )
        self.window.recovery_manager = self.session_store
        self.window.autosave_coordinator = MagicMock()
        self.window._autosave_generation = 1

    def test_AS25_queue_project_switch_rebinds_recovery_before_b_autosave(self):
        video_b = str(Path(self.temp_dir.name) / "video-b.mp4")
        project_b_dir = Path(self.temp_dir.name) / "project-b.ai-subtitle"
        project_b = SimpleNamespace(
            project_id="project-b",
            source=SimpleNamespace(path=video_b, fingerprint="fp-b", modified_at=0.0),
        )
        self.project_service.current_project = SimpleNamespace(
            project_id="project-a",
            source=SimpleNamespace(path="video-a.mp4", fingerprint="fp-a", modified_at=0.0),
        )
        self.project_service.project_dir = str(
            Path(self.temp_dir.name) / "project-a.ai-subtitle"
        )
        self.project_service.current_project_id = None
        self.project_service.requires_project_switch.return_value = True
        events = []

        def create_project(_project_dir, _name, _video_path):
            events.append("create-project-b")
            self.project_service.current_project = project_b
            self.project_service.project_dir = str(project_b_dir)
            return project_b

        self.project_service.create_project.side_effect = create_project
        self.window.autosave_coordinator.clear_session.side_effect = (
            lambda: events.append("clear-autosave-a")
        )
        self.window.autosave_coordinator.bind_session.side_effect = (
            lambda session_id: events.append(f"bind-{session_id}")
        )
        self.window.queue_mgr = MagicMock()
        self.window.queue_mgr.get_active_data.return_value = (video_b, None)
        self.window.queue_mgr.get_items.return_value = {video_b: {"duration": 0}}
        self.window.video_player = MagicMock()
        self.window.out_input.setText(self.temp_dir.name)

        with patch.object(self.window, "_sync_subtitle_placement_from_project"), \
                patch.object(self.window.generation_panel, "check_resumable_state"), \
                patch.object(self.window, "_refresh_transcription_context_views"), \
                patch("ui.Gui.threading.Thread") as thread_cls:
            thread_cls.return_value.start = MagicMock()
            self.window.on_queue_item_clicked(video_b)

        self.assertEqual(events[:2], ["clear-autosave-a", "create-project-b"])
        self.assertEqual(self.session_store._active_session.manifest.project_id, "project-b")
        self.assertEqual(
            self.window._autosave_session_identity()["session_id"], "session-project-b"
        )
        self.window.sub_editor.all_segments = [
            {"id": "b-segment", "text": "Project B"}
        ]
        with patch.object(self.window.workspace_service, "capture_workspace", return_value={}):
            captured = self.window.capture_recovery_working_state()
        self.assertEqual(captured.session_id, "session-project-b")
        self.assertEqual(captured.project_id, "project-b")
        self.assertEqual(captured.segments[0]["text"], "Project B")

        scheduler = _Scheduler()

        def persist(state):
            self.session_store.snapshots.append(state)
            self.window.revision_tracker.record_snapshot_success(state.edit_revision)
            return True

        coordinator = AutosaveCoordinator(
            revision_tracker=self.window.revision_tracker,
            session_provider=self.window._autosave_session_identity,
            snapshot_provider=self.window.capture_recovery_working_state,
            persist_snapshot=persist,
            scheduler=scheduler,
        )
        self.window.autosave_coordinator = coordinator
        self.addCleanup(coordinator.dispose)
        self.window.workspace_service.capture_workspace = MagicMock(return_value={})
        self.window.revision_tracker.record_external_change()
        coordinator.start()
        scheduler.advance(30_000)

        self.assertEqual(len(self.session_store.snapshots), 1)
        self.assertEqual(self.session_store.snapshots[0].session_id, "session-project-b")
        self.assertEqual(self.session_store.snapshots[0].project_id, "project-b")


if __name__ == "__main__":
    unittest.main()
