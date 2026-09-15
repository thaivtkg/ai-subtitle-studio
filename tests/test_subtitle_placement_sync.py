import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestSubtitlePlacementSyncContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_r1_inspector_user_edit_commits_project_state(self):
        from core.project.project_state import ProjectState
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow

        project = SimpleNamespace(state=ProjectState())
        service = ProjectService()
        window = MainWindow(
            project_service=service,
            media_import_service=MagicMock(),
        )
        service.current_project = project
        service.mark_dirty = MagicMock()

        panel = window.inspector_panel

        panel.cmb_position.setCurrentText("Custom")
        panel.spin_x.setValue(15.3)
        panel.spin_x.editingFinished.emit()
        panel.spin_y.setValue(76.2)
        panel.spin_y.editingFinished.emit()

        placement = project.state.subtitle_placement
        self.assertEqual(placement.mode, "custom")
        self.assertAlmostEqual(placement.x, 0.153)
        self.assertAlmostEqual(placement.y, 0.762)
        window.close()

    def test_r2a_drag_commit_handler_updates_project_state_before_worker_handoff(self):
        from core.project.project_state import ProjectState
        from core.services.project_service import ProjectService
        from core.subtitle_placement import SubtitlePlacementState
        from ui.Gui import MainWindow
        from workers.TaskQueue import HardsubWorker

        project_state = ProjectState()
        project = SimpleNamespace(state=project_state)
        service = ProjectService()
        window = MainWindow(
            project_service=service,
            media_import_service=MagicMock(),
        )
        service.current_project = project
        service.mark_dirty = MagicMock()

        handler = getattr(window, "_on_subtitle_placement_committed", None)
        self.assertTrue(callable(handler), "production drag commit handler is missing")

        from PySide6.QtCore import QObject, Signal

        class DragCommitSource(QObject):
            committed = Signal(object)

        source = DragCommitSource()
        source.committed.connect(handler)
        final_placement = SubtitlePlacementState(mode="custom", x=0.153, y=0.762)
        source.committed.emit(final_placement)

        self.assertEqual(project_state.subtitle_placement, final_placement)

        worker = HardsubWorker(
            "video.mp4",
            "source.srt",
            "output",
            42,
            "white",
            "Arial",
            project_state=project_state,
        )
        self.assertEqual(worker.project_state.subtitle_placement, final_placement)
        window.close()

    def test_r2b_production_overlay_signal_is_wired_to_main_window_handler(self):
        from core.project.project_state import ProjectState
        from core.services.project_service import ProjectService
        from core.subtitle_placement import SubtitlePlacementState
        from ui.Gui import MainWindow

        service = ProjectService()
        window = MainWindow(
            project_service=service,
            media_import_service=MagicMock(),
        )
        project = SimpleNamespace(state=ProjectState())
        service.current_project = project
        service.mark_dirty = MagicMock()

        final_placement = SubtitlePlacementState(mode="custom", x=0.153, y=0.762)
        window.video_player.subtitle_placement_committed.emit(final_placement)

        self.assertEqual(project.state.subtitle_placement, final_placement)
        window.close()

    def test_r2c_production_overlay_drag_reaches_project_state(self):
        from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
        from PySide6.QtGui import QMouseEvent

        from core.project.project_state import ProjectState
        from core.services.project_service import ProjectService
        from ui.Gui import MainWindow
        from ui.animations.animation_types import SubtitleRenderInput

        service = ProjectService()
        window = MainWindow(
            project_service=service,
            media_import_service=MagicMock(),
        )
        project = SimpleNamespace(state=ProjectState())
        service.current_project = project
        service.mark_dirty = MagicMock()

        player = window.video_player
        overlay = player.subtitle_overlay
        overlay.resize(640, 360)
        overlay.update_subtitle(
            SubtitleRenderInput(
                segment_id=1,
                start_ms=0,
                end_ms=1000,
                text="line one\nline two",
            ),
            500,
        )
        player.view.resize(640, 360)
        player.view.scene().setSceneRect(0, 0, 640, 360)
        player.overlay_proxy.setGeometry(QRectF(0, 0, 640, 360))
        player.set_position_edit_mode(True)

        layout = overlay.calculate_layout()
        self.assertIsNotNone(layout)
        overlay_origin = player.overlay_proxy.geometry().topLeft()
        press_local = layout.rendered_bounds.center()
        press_scene = overlay_origin + press_local
        press_view = player.view.mapFromScene(press_scene)

        target_anchor = QPointF(640 * 0.25, 360 * 0.75)
        drag_offset = layout.base_anchor - press_local
        release_scene = overlay_origin + target_anchor - drag_offset
        release_view = player.view.mapFromScene(release_scene)
        viewport = player.view.viewport()

        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(press_view),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(release_view),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(release_view),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        player.eventFilter(viewport, press)
        player.eventFilter(viewport, move)
        player.eventFilter(viewport, release)

        placement = project.state.subtitle_placement
        self.assertEqual(placement.mode, "custom")
        self.assertAlmostEqual(placement.x, 0.25, delta=0.02)
        self.assertAlmostEqual(placement.y, 0.75, delta=0.02)
        window.close()

    def test_r3_project_restore_syncs_overlay_and_inspector_without_dirty(self):
        from PySide6.QtWidgets import QApplication

        from core.services.project_service import ProjectService
        from core.subtitle_placement import SubtitlePlacementState
        from core.runtime.single_instance_guard import IpcAction, IpcRequest
        from ui.Gui import MainWindow

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_fixture = (
                Path(__file__).parents[1]
                / "resources"
                / "tutorials"
                / "assets"
                / "getting_started_generation.gif"
            )
            self.assertTrue(media_fixture.is_file(), "valid media fixture is missing")
            project_dir = root / "restore.ai-subtitle"

            service = ProjectService()
            project = service.create_project(str(project_dir), "Restore", str(media_fixture))
            project.state.subtitle_placement = SubtitlePlacementState(
                mode="custom", x=0.153, y=0.762
            )
            service.save_project()
            service.current_project = None

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            before_revision = window.revision_tracker.edit_revision
            before_dirty = window.revision_tracker.is_dirty
            window.video_player.subtitle_overlay.set_placement_state("bottom", 0.5, 0.85)
            window.inspector_panel.set_placement_state("bottom", 0.5, 0.85, emit=False)
            window.workspace_service.restore_workspace = MagicMock()
            window._refresh_transcription_context_views = MagicMock()

            window.handle_ipc_request(
                IpcRequest(IpcAction.OPEN_PROJECT, str(project_dir))
            )
            QApplication.processEvents()

            overlay_placement = window.video_player.subtitle_overlay.placement_state
            inspector_style = window.inspector_panel.get_current_style()
            self.assertEqual(
                (overlay_placement.mode, overlay_placement.x, overlay_placement.y),
                ("custom", 0.153, 0.762),
            )
            self.assertEqual(inspector_style["position"], "custom")
            self.assertAlmostEqual(inspector_style["x"], 0.153)
            self.assertAlmostEqual(inspector_style["y"], 0.762)
            self.assertEqual(window.revision_tracker.edit_revision, before_revision)
            self.assertEqual(window.revision_tracker.is_dirty, before_dirty)
            window.close()

    def test_r4_queue_project_switch_restores_placement_without_dirty(self):
        from core.project.project_state import ProjectState
        from core.services.project_service import ProjectService
        from core.subtitle_placement import SubtitlePlacementState
        from ui.Gui import MainWindow

        media_fixture = (
            Path(__file__).parents[1]
            / "resources"
            / "tutorials"
            / "assets"
            / "getting_started_generation.gif"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_a = root / "video_a.gif"
            video_b = root / "video_b.gif"
            shutil.copyfile(media_fixture, video_a)
            shutil.copyfile(media_fixture, video_b)

            service = ProjectService()
            project_a_dir = root / "project_a.ai-subtitle"
            project_b_dir = root / "project_b.ai-subtitle"
            project_a = service.create_project(
                str(project_a_dir), "Project A", str(video_a)
            )
            project_a.state.subtitle_placement = SubtitlePlacementState(
                mode="custom", x=0.153, y=0.762
            )
            service.save_project()
            project_b = service.create_project(
                str(project_b_dir), "Project B", str(video_b)
            )
            self.assertEqual(
                project_b.state.subtitle_placement,
                SubtitlePlacementState(),
            )
            service.open_project(str(project_a_dir))

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window.video_player.subtitle_overlay.set_placement_state(
                "custom", 0.153, 0.762
            )
            window.inspector_panel.set_placement_state(
                "custom", 0.153, 0.762, emit=False
            )
            window.queue_mgr._items = {
                str(video_a): {"srt_path": None, "duration": 0},
                str(video_b): {"srt_path": None, "duration": 0},
            }
            window.queue_mgr.active_vid = str(video_a)
            window._queue_project_dirs = {
                str(video_a): str(project_a_dir),
                str(video_b): str(project_b_dir),
            }
            before_revision = window.revision_tracker.edit_revision
            before_dirty = window.revision_tracker.is_dirty

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(str(video_b))

            placement = service.current_project.state.subtitle_placement
            overlay_placement = window.video_player.subtitle_overlay.placement_state
            inspector_style = window.inspector_panel.get_current_style()
            self.assertEqual(placement, SubtitlePlacementState())
            self.assertEqual(
                (overlay_placement.mode, overlay_placement.x, overlay_placement.y),
                ("bottom", 0.5, 0.85),
            )
            self.assertEqual(inspector_style["position"], "bottom")
            self.assertAlmostEqual(inspector_style["x"], 0.5)
            self.assertAlmostEqual(inspector_style["y"], 0.85)
            self.assertEqual(window.revision_tracker.edit_revision, before_revision)
            self.assertEqual(window.revision_tracker.is_dirty, before_dirty)
            window.revision_tracker.reset_for_new_document()
            window.close()

    def test_r5_fresh_queue_project_resets_stale_placement_without_dirty(self):
        from core.services.project_service import ProjectService
        from core.subtitle_placement import SubtitlePlacementState
        from ui.Gui import MainWindow

        media_fixture = (
            Path(__file__).parents[1]
            / "resources"
            / "tutorials"
            / "assets"
            / "getting_started_generation.gif"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            previous_video = root / "previous.gif"
            fresh_video = root / "fresh.gif"
            shutil.copyfile(media_fixture, previous_video)
            shutil.copyfile(media_fixture, fresh_video)

            service = ProjectService()
            previous_dir = root / "previous.ai-subtitle"
            service.create_project(str(previous_dir), "Previous", str(previous_video))
            service.current_project.state.subtitle_placement = SubtitlePlacementState(
                mode="custom", x=0.153, y=0.762
            )
            service.save_project()

            window = MainWindow(
                project_service=service,
                media_import_service=MagicMock(),
            )
            window.video_player.load_video = MagicMock()
            window.generation_panel.check_resumable_state = MagicMock()
            window._refresh_transcription_context_views = MagicMock()
            window.video_player.subtitle_overlay.set_placement_state(
                "custom", 0.153, 0.762
            )
            window.inspector_panel.set_placement_state(
                "custom", 0.153, 0.762, emit=False
            )
            window.queue_mgr._items = {
                str(fresh_video): {"srt_path": None, "duration": 0},
            }
            window.queue_mgr.active_vid = str(fresh_video)
            before_revision = window.revision_tracker.edit_revision
            before_dirty = window.revision_tracker.is_dirty

            with patch("ui.Gui.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                window.on_queue_item_clicked(
                    str(fresh_video), fresh_project=True
                )

            placement = service.current_project.state.subtitle_placement
            overlay_placement = window.video_player.subtitle_overlay.placement_state
            inspector_style = window.inspector_panel.get_current_style()
            self.assertEqual(placement, SubtitlePlacementState())
            self.assertEqual(
                (overlay_placement.mode, overlay_placement.x, overlay_placement.y),
                ("bottom", 0.5, 0.85),
            )
            self.assertEqual(inspector_style["position"], "bottom")
            self.assertAlmostEqual(inspector_style["x"], 0.5)
            self.assertAlmostEqual(inspector_style["y"], 0.85)
            self.assertEqual(window.revision_tracker.edit_revision, before_revision)
            self.assertEqual(window.revision_tracker.is_dirty, before_dirty)
            window.revision_tracker.reset_for_new_document()
            window.close()


if __name__ == "__main__":
    unittest.main()
