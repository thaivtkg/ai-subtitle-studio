import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMainWindow

from core.services.workspace_service import WorkspaceService
from player.video_player import VideoPlayerWidget
from ui.Gui import MainWindow


class TestSubtitlePreviewRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_editor_host(self, text="Subtitle Preview"):
        host = QMainWindow()
        host.sub_editor = SimpleNamespace(
            all_segments=[
                {
                    "start": "00:00:01,000",
                    "end": "00:00:03,000",
                    "text": text,
                    "stt": 1,
                }
            ],
            highlight_row_by_stt=MagicMock(),
            clear_highlight=MagicMock(),
        )
        return host

    def _make_preview_window(self, enabled=True):
        window = MainWindow.__new__(MainWindow)
        window.video_player = SimpleNamespace(
            sub_controller=SimpleNamespace(is_enabled=enabled),
            subtitle_overlay=MagicMock(),
            player=MagicMock(position=MagicMock(return_value=1500)),
            position_changed=MagicMock(),
        )
        window.inspector_panel = SimpleNamespace(chk_preview=MagicMock())
        return window

    def _render_overlay(self, player):
        image = QImage(player.subtitle_overlay.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        player.subtitle_overlay.render(image)
        return image

    def test_position_changed_renders_editor_subtitle(self):
        host = self._make_editor_host()
        player = VideoPlayerWidget(host)
        host.setCentralWidget(player)
        host.resize(960, 540)
        host.show()
        player.empty_state_lbl.hide()
        self.app.processEvents()

        player.position_changed(1500)

        self.assertIsNotNone(player.subtitle_overlay.render_input)
        self.assertEqual(player.subtitle_overlay.render_input.text, "Subtitle Preview")
        self.assertTrue(player.subtitle_overlay.isVisible())
        self.assertTrue(player.overlay_proxy.isVisible())
        self.assertGreater(player.subtitle_overlay.width(), 0)
        self.assertGreater(player.subtitle_overlay.height(), 0)
        self.assertGreater(player.overlay_proxy.geometry().width(), 0)
        self.assertGreater(player.overlay_proxy.geometry().height(), 0)
        self.assertGreater(player.overlay_proxy.zValue(), player.video_item.zValue())
        host.close()
        host.deleteLater()
        self.app.processEvents()

    def test_actual_overlay_paint_changes_pixels_for_ascii_and_cjk(self):
        for text in ("Subtitle Preview", "出たなボンネン！"):
            with self.subTest(text=text):
                host = self._make_editor_host(text)
                player = VideoPlayerWidget(host)
                host.setCentralWidget(player)
                host.resize(960, 540)
                host.show()
                player.empty_state_lbl.hide()
                self.app.processEvents()

                before = self._render_overlay(player)
                player.position_changed(1500)
                self.app.processEvents()
                after = self._render_overlay(player)

                self.assertNotEqual(before, after)
                host.close()
                host.deleteLater()
                self.app.processEvents()

    def test_actual_graphics_view_paint_changes_pixels(self):
        host = self._make_editor_host()
        player = VideoPlayerWidget(host)
        host.setCentralWidget(player)
        host.resize(960, 540)
        host.show()
        player.empty_state_lbl.hide()
        self.app.processEvents()

        before = player.view.grab().toImage()
        player.position_changed(1500)
        self.app.processEvents()
        after = player.view.grab().toImage()

        self.assertNotEqual(before, after)
        host.close()
        host.deleteLater()
        self.app.processEvents()

    def test_turning_preview_on_uses_real_main_window_transition(self):
        window = self._make_preview_window(enabled=False)

        window._on_preview_toggled(True)

        self.assertTrue(window.video_player.sub_controller.is_enabled)
        window.video_player.subtitle_overlay.setVisible.assert_called_once_with(True)
        window.video_player.position_changed.assert_called_once_with(1500)
        window.inspector_panel.chk_preview.setChecked.assert_called_once_with(True)

    def test_turning_preview_off_uses_real_main_window_transition(self):
        window = self._make_preview_window(enabled=True)

        window._on_preview_toggled(False)

        self.assertFalse(window.video_player.sub_controller.is_enabled)
        window.video_player.subtitle_overlay.setVisible.assert_called_once_with(False)
        window.video_player.subtitle_overlay.clear_subtitle.assert_called_once_with()
        window.inspector_panel.chk_preview.setChecked.assert_called_once_with(False)

    def _workspace_service(self, enabled):
        window = self._make_preview_window(enabled=not enabled)
        project = SimpleNamespace(
            state=SimpleNamespace(
                active_artifact_id=None,
                workspace=SimpleNamespace(
                    active_page="dashboard",
                    active_tab="inline_editor",
                    subtitle_preview_enabled=enabled,
                    playback_position_ms=0,
                ),
            ),
            source=SimpleNamespace(path="requirements.txt"),
        )
        window.switch_page = MagicMock()
        window.bottom_tabs = SimpleNamespace(setCurrentIndex=MagicMock())
        window.queue_mgr = SimpleNamespace(
            get_items=MagicMock(return_value=[]),
            add_video=MagicMock(),
        )
        window.on_queue_item_clicked = MagicMock()
        service = WorkspaceService(window, SimpleNamespace(current_project=project))
        return window, service

    def test_restore_workspace_preview_false_syncs_all_layers(self):
        window, service = self._workspace_service(False)

        service.restore_workspace()

        self.assertFalse(window.video_player.sub_controller.is_enabled)
        window.video_player.subtitle_overlay.setVisible.assert_called_once_with(False)
        window.inspector_panel.chk_preview.setChecked.assert_called_once_with(False)

    def test_restore_workspace_preview_true_syncs_all_layers(self):
        window, service = self._workspace_service(True)

        service.restore_workspace()

        self.assertTrue(window.video_player.sub_controller.is_enabled)
        window.video_player.subtitle_overlay.setVisible.assert_called_once_with(True)
        window.inspector_panel.chk_preview.setChecked.assert_called_once_with(True)

    def test_timeline_position_still_emits_when_preview_is_off(self):
        host = self._make_editor_host()
        player = VideoPlayerWidget(host)
        player.sub_controller.is_enabled = False
        emitted = []
        player.timeline_position_changed.connect(emitted.append)

        player.position_changed(1500)

        self.assertEqual(emitted, [1500])


if __name__ == "__main__":
    unittest.main()
