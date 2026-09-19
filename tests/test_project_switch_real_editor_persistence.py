import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestProjectSwitchRealEditorPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_queue_signal_switch_persists_live_table_editor_content(self):
        from PySide6.QtWidgets import QApplication, QLineEdit
        from core.artifacts.artifact import Artifact
        from core.artifacts.artifact_types import ArtifactStatus, ArtifactType
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_a = root / "video-a.mp4"
            video_b = root / "video-b.mp4"
            video_a.write_bytes(b"video-a")
            video_b.write_bytes(b"video-b")
            srt_a = root / "a.srt"
            srt_b = root / "b.srt"
            srt_a.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\noriginal A\n",
                encoding="utf-8",
            )
            srt_b.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nproject B\n",
                encoding="utf-8",
            )

            service = ProjectService()
            project_a_dir = root / "project-a.ai-subtitle"
            project_b_dir = root / "project-b.ai-subtitle"
            project_a = service.create_project(
                str(project_a_dir), "Project A", str(video_a)
            )
            artifact_a = Artifact(
                artifact_id="artifact-a",
                artifact_type=ArtifactType.TIMING,
                path=str(srt_a),
                created_at="now",
                updated_at="now",
                source_project_id=project_a.project_id,
                status=ArtifactStatus.READY,
            )
            service.artifact_store.register(artifact_a)
            project_a.state.active_artifact_id = artifact_a.artifact_id
            service.save_project()

            project_b = service.create_project(
                str(project_b_dir), "Project B", str(video_b)
            )
            artifact_b = Artifact(
                artifact_id="artifact-b",
                artifact_type=ArtifactType.TIMING,
                path=str(srt_b),
                created_at="now",
                updated_at="now",
                source_project_id=project_b.project_id,
                status=ArtifactStatus.READY,
            )
            service.artifact_store.register(artifact_b)
            project_b.state.active_artifact_id = artifact_b.artifact_id
            service.save_project()
            service.open_project(str(project_a_dir))

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            self.addCleanup(window.close)
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window._sync_subtitle_placement_from_project = MagicMock()
            window.queue_mgr._items = {
                str(video_a): {"srt_path": str(srt_a), "duration": 0},
                str(video_b): {"srt_path": str(srt_b), "duration": 0},
            }
            window.queue_mgr.active_vid = str(video_a)
            window._queue_project_dirs = {
                str(video_a): str(project_a_dir),
                str(video_b): str(project_b_dir),
            }
            window.sub_editor.load_srt_file(str(srt_a))
            window.sub_editor.select_segment(0)
            window.revision_tracker.reset_for_new_document()
            window.canonical_save_coordinator.cancel_pending()

            table = window.sub_editor.table
            table.editItem(table.item(0, 4))
            QApplication.processEvents()
            cell_editor = table.findChild(QLineEdit)
            self.assertIsNotNone(cell_editor)
            cell_editor.setText("E2_SWITCH_CONTENT")
            self.assertEqual(table.item(0, 4).text(), "original A")
            self.assertEqual(window.sub_editor.all_segments[0]["text"], "original A")
            self.assertFalse(window.revision_tracker.is_dirty)

            events = []
            original_save = service.save_project
            original_open = service.open_project

            def save_project():
                events.append(f"save:{service.current_project.name}")
                return original_save()

            def open_project(path):
                events.append(f"open:{Path(path).name}")
                return original_open(path)

            service.save_project = save_project
            service.open_project = open_project
            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.queue_ui.item_clicked.emit(str(video_b))

            self.assertLess(
                events.index("save:Project A"),
                events.index("open:project-b.ai-subtitle"),
            )
            self.assertIn("E2_SWITCH_CONTENT", srt_a.read_text(encoding="utf-8"))
            window.queue_ui.item_clicked.emit(str(video_a))
            self.assertEqual(
                window.sub_editor.all_segments[0]["text"], "E2_SWITCH_CONTENT"
            )


if __name__ == "__main__":
    unittest.main()
