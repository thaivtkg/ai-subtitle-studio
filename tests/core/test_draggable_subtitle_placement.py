import os
import tempfile
import unittest
from pathlib import Path


class TestDraggableSubtitlePlacementContracts(unittest.TestCase):
    def _placement_api(self):
        import core

        api = getattr(core, "subtitle_placement", None)
        self.assertIsNotNone(api, "normalized placement contract is missing")
        return api

    def _overlay(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from player.subtitle_overlay import SubtitleOverlay
        from ui.animations.animation_types import SubtitleRenderInput

        app = QApplication.instance() or QApplication([])
        overlay = SubtitleOverlay()
        overlay.resize(640, 360)
        overlay.update_subtitle(
            SubtitleRenderInput(
                segment_id=1,
                start_ms=0,
                end_ms=1000,
                text="line one\nline two",
            ),
            0,
        )
        return app, overlay

    def test_normalized_anchor_maps_to_video_pixels(self):
        api = self._placement_api()
        self.assertEqual(api.normalized_to_pixel_anchor(1920, 1080, 0.25, 0.75), (480, 810))

    def test_multiline_rendered_bounds_are_clamped_inside_video(self):
        app, overlay = self._overlay()
        self.assertTrue(hasattr(overlay, "set_placement_state"), "overlay placement API is missing")
        self.assertTrue(hasattr(overlay, "calculate_layout"), "shared overlay layout API is missing")
        overlay.set_placement_state("custom", 0.99, 0.99)
        layout = overlay.calculate_layout()
        self.assertTrue(overlay.is_inside_video(layout.rendered_bounds))
        app.processEvents()

    def test_resize_preserves_normalized_anchor(self):
        api = self._placement_api()
        self.assertEqual(api.normalized_to_pixel_anchor(1920, 1080, 0.25, 0.75), (480, 810))
        self.assertEqual(api.normalized_to_pixel_anchor(1280, 720, 0.25, 0.75), (320, 540))

    def test_hit_test_uses_rendered_subtitle_bounds(self):
        app, overlay = self._overlay()
        self.assertTrue(hasattr(overlay, "calculate_layout"), "shared overlay layout API is missing")
        self.assertTrue(hasattr(overlay, "hit_test"), "overlay hit-test API is missing")
        layout = overlay.calculate_layout()
        self.assertTrue(overlay.hit_test(layout.rendered_bounds.center()))
        self.assertFalse(overlay.hit_test((0, 0)))
        app.processEvents()

    def test_drag_completion_changes_preset_to_custom(self):
        api = self._placement_api()
        placement = api.SubtitlePlacementState(mode="bottom")
        updated = api.complete_drag(placement, 0.25, 0.75)
        self.assertEqual((updated.mode, updated.x, updated.y), ("custom", 0.25, 0.75))

    def test_switching_away_from_custom_retains_custom_coordinates(self):
        api = self._placement_api()
        placement = api.SubtitlePlacementState(mode="custom", x=0.25, y=0.75)
        placement = api.set_mode(placement, "bottom")
        placement = api.set_mode(placement, "custom")
        self.assertEqual((placement.x, placement.y), (0.25, 0.75))

    def test_inspector_programmatic_sync_does_not_emit_user_edit(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from ui.subtitle_inspector_panel import SubtitleInspectorPanel

        app = QApplication.instance() or QApplication([])
        panel = SubtitleInspectorPanel()
        emitted = []
        panel.style_changed.connect(emitted.append)
        self.assertTrue(hasattr(panel, "set_placement_state"), "guarded inspector sync API is missing")
        panel.set_placement_state("custom", 0.25, 0.75, emit=False)
        self.assertEqual(emitted, [])
        self.assertEqual(panel.get_current_style()["position"], "custom")
        del app

    def test_project_persistence_round_trip(self):
        from core.services.project_service import ProjectService

        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "video.mp4"
            video_path.write_bytes(b"test video")
            project_dir = Path(temp_dir) / "project.ai-subtitle"
            service = ProjectService()
            project = service.create_project(str(project_dir), "Test", str(video_path))
            self.assertTrue(hasattr(project.state, "subtitle_placement"), "project placement state is missing")
            project.state.subtitle_placement.mode = "custom"
            project.state.subtitle_placement.x = 0.25
            project.state.subtitle_placement.y = 0.75
            service.save_project()

            reopened = service.open_project(str(project_dir))
            placement = reopened.state.subtitle_placement
            self.assertEqual((placement.mode, placement.x, placement.y), ("custom", 0.25, 0.75))

    def test_legacy_project_defaults_to_bottom(self):
        from core.project.project_state import ProjectState

        self.assertTrue(hasattr(ProjectState(), "subtitle_placement"), "legacy placement default is missing")
        placement = ProjectState().subtitle_placement
        self.assertEqual((placement.mode, placement.x, placement.y), ("bottom", 0.5, 0.85))

    def test_drag_moves_commit_dirty_state_only_on_release(self):
        api = self._placement_api()
        commits = []
        session = api.PlacementEditSession(on_commit=commits.append)
        session.move(0.2, 0.7)
        session.move(0.25, 0.75)
        self.assertEqual(commits, [])
        session.release()
        self.assertEqual(len(commits), 1)
        self.assertEqual((commits[0].x, commits[0].y), (0.25, 0.75))

if __name__ == "__main__":
    unittest.main()
