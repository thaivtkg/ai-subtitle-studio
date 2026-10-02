import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestQueueProjectIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_same_video_can_have_two_explicit_project_bindings(self):
        from core.queue_manager import QueueManager

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "shared.mp4"
            video.write_bytes(b"video")
            project_a = root / "A.ai-subtitle"
            project_a.mkdir()
            project_b = root / "B.ai-subtitle"
            project_b.mkdir()

            queue = QueueManager()
            self.assertTrue(
                queue.add_video(
                    str(video),
                    project_id="A-ID",
                    project_root=str(project_a),
                )
            )
            self.assertTrue(
                queue.add_video(
                    str(video),
                    project_id="B-ID",
                    project_root=str(project_b),
                )
            )

            items = queue.get_items()
            self.assertEqual(len(items), 2)
            bindings = {
                (data["project_id"], os.path.normcase(data["project_root"]))
                for data in items.values()
            }
            self.assertEqual(
                bindings,
                {
                    ("A-ID", os.path.normcase(str(project_a))),
                    ("B-ID", os.path.normcase(str(project_b))),
                },
            )

    def test_unbound_video_is_bound_once_and_reused(self):
        from core.queue_manager import QueueManager

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "raw.mp4"
            video.write_bytes(b"video")
            project = root / "raw.ai-subtitle"
            project.mkdir()

            queue = QueueManager()
            self.assertTrue(queue.add_video(str(video)))
            item_key = queue.ensure_project_binding(
                str(video), project_id="RAW-ID", project_root=str(project)
            )
            self.assertIsNotNone(item_key)
            same_key = queue.ensure_project_binding(
                str(video), project_id="RAW-ID", project_root=str(project)
            )

            self.assertEqual(item_key, same_key)
            self.assertEqual(queue.get_item(item_key)["project_id"], "RAW-ID")
            self.assertEqual(len(queue.get_items()), 1)

            other_project = root / "other.ai-subtitle"
            other_project.mkdir()
            other_key = queue.ensure_project_binding(
                str(video), project_id="OTHER-ID", project_root=str(other_project)
            )
            self.assertNotEqual(item_key, other_key)
            self.assertEqual(len(queue.get_items()), 2)

    def test_bound_queue_item_reopens_exact_project_for_shared_video(self):
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "shared.mp4"
            video.write_bytes(b"video")
            project_a_dir = root / "A.ai-subtitle"
            project_a2_dir = root / "A2.ai-subtitle"

            service = ProjectService()
            project_a = service.create_project(
                str(project_a_dir), "Project A", str(video)
            )
            project_a2 = service.create_project(
                str(project_a2_dir), "Project A2", str(video)
            )
            service.open_project(str(project_a2_dir))

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            self.addCleanup(window.close)
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window._sync_subtitle_placement_from_project = MagicMock()
            window._prepare_recovery_session_switch = MagicMock(return_value=True)
            window._complete_recovery_session_switch = MagicMock()

            item_a = window.queue_mgr.ensure_project_binding(
                str(video), project_id=project_a.project_id, project_root=str(project_a_dir)
            )
            item_a2 = window.queue_mgr.ensure_project_binding(
                str(video), project_id=project_a2.project_id, project_root=str(project_a2_dir)
            )
            window.queue_mgr.set_active(item_a2)

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(item_a)

            self.assertEqual(service.current_project.project_id, project_a.project_id)
            self.assertEqual(
                os.path.normcase(service.project_dir),
                os.path.normcase(str(project_a_dir)),
            )

    def test_unbound_queue_click_auto_creates_once_then_reuses_binding(self):
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "raw.mp4"
            video.write_bytes(b"video")

            service = ProjectService()
            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            self.addCleanup(window.close)
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window._sync_subtitle_placement_from_project = MagicMock()
            window._prepare_recovery_session_switch = MagicMock(return_value=True)
            window._complete_recovery_session_switch = MagicMock()
            window.out_input.setText(str(root))
            self.assertTrue(window.queue_mgr.add_video(str(video)))

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(str(video))
            first_project_id = service.current_project.project_id
            first_project_dir = service.project_dir

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(str(video))

            item = window.queue_mgr.get_item(str(video))
            self.assertEqual(item["project_id"], first_project_id)
            self.assertEqual(
                os.path.normcase(item["project_root"]),
                os.path.normcase(first_project_dir),
            )
            self.assertEqual(service.current_project.project_id, first_project_id)
            self.assertEqual(len(window.queue_mgr.get_items()), 1)

    def test_shared_video_switch_keeps_project_owned_artifact_after_cold_reload(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication, QLineEdit
        from core.artifacts.artifact import Artifact
        from core.artifacts.artifact_types import ArtifactStatus, ArtifactType
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "shared.mp4"
            video.write_bytes(b"video")
            source_srt = root / "shared.srt"
            source_srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\noriginal\n",
                encoding="utf-8",
            )
            project_a_dir = root / "A.ai-subtitle"
            project_a2_dir = root / "A2.ai-subtitle"

            service = ProjectService()
            project_a = service.create_project(
                str(project_a_dir), "Project A", str(video)
            )
            artifact = Artifact(
                artifact_id="shared-artifact",
                artifact_type=ArtifactType.TIMING,
                path=str(source_srt),
                created_at="now",
                updated_at="now",
                source_project_id=project_a.project_id,
                status=ArtifactStatus.READY,
            )
            service.artifact_store.register(artifact)
            project_a.state.active_artifact_id = artifact.artifact_id
            service.save_project()
            project_a2 = service.create_project(
                str(project_a2_dir), "Project A2", str(video)
            )
            service.open_project(str(project_a_dir))

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )

            def cleanup_window():
                window.autosave_coordinator.dispose()
                window.canonical_save_coordinator.dispose()
                window._canonical_status_timer.stop()
                window.close()
                window.deleteLater()
                QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                QApplication.processEvents()

            self.addCleanup(cleanup_window)
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window._sync_subtitle_placement_from_project = MagicMock()
            window._complete_recovery_session_switch = MagicMock()
            item_a = window.queue_mgr.ensure_project_binding(
                str(video), project_id=project_a.project_id, project_root=str(project_a_dir)
            )
            item_a2 = window.queue_mgr.ensure_project_binding(
                str(video), project_id=project_a2.project_id, project_root=str(project_a2_dir)
            )
            window.queue_mgr.set_active(item_a)
            window.sub_editor.load_srt_file(str(source_srt))
            window.sub_editor.select_segment(0)
            window.revision_tracker.reset_for_new_document()
            window.canonical_save_coordinator.cancel_pending()

            table = window.sub_editor.table
            table.editItem(table.item(0, 4))
            QApplication.processEvents()
            editor = table.findChild(QLineEdit)
            self.assertIsNotNone(editor)
            editor.setText("E5_PROJECT_IDENTITY_TOKEN")

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(item_a2)

            self.assertEqual(service.current_project.project_id, project_a2.project_id)
            project_owned = project_a_dir / "artifacts" / "timing" / source_srt.name
            self.assertTrue(project_owned.exists())
            self.assertIn("E5_PROJECT_IDENTITY_TOKEN", project_owned.read_text(encoding="utf-8"))

            cold_service = ProjectService()
            cold_project = cold_service.open_project(str(project_a_dir))
            cold_artifact = cold_service.artifact_store.get(
                cold_project.state.active_artifact_id
            )
            self.assertIsNotNone(cold_artifact)
            self.assertEqual(Path(cold_artifact.path), project_owned)
            self.assertIn("E5_PROJECT_IDENTITY_TOKEN", Path(cold_artifact.path).read_text(encoding="utf-8"))

    def test_workspace_restore_binds_loaded_project_before_queue_activation(self):
        from types import SimpleNamespace
        from core.queue_manager import QueueManager
        from core.services.project_service import ProjectService
        from core.services.workspace_service import WorkspaceService

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "restore.mp4"
            video.write_bytes(b"video")
            project_dir = root / "restore.ai-subtitle"
            service = ProjectService()
            project = service.create_project(str(project_dir), "Restore", str(video))

            ui = SimpleNamespace(
                queue_mgr=QueueManager(),
                project_service=service,
                switch_page=MagicMock(),
                bottom_tabs=None,
                video_player=SimpleNamespace(
                    sub_controller=SimpleNamespace(), player=None
                ),
                set_subtitle_preview_enabled=MagicMock(),
                on_queue_item_clicked=MagicMock(),
            )
            WorkspaceService(ui, service).restore_workspace()

            item = ui.queue_mgr.get_item(str(video))
            self.assertEqual(item["project_id"], project.project_id)
            self.assertEqual(
                os.path.normcase(item["project_root"]),
                os.path.normcase(str(project_dir)),
            )
            ui.on_queue_item_clicked.assert_called_once_with(
                ui.queue_mgr.get_item_key(str(video)),
                project_id=project.project_id,
                project_root=str(project_dir),
            )


if __name__ == "__main__":
    unittest.main()
