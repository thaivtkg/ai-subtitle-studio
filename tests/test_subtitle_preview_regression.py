import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QMainWindow

from core.services.workspace_service import WorkspaceService
from ui.Gui import MainWindow
from player.video_player import VideoPlayerWidget


class PreviewHost:
    def __init__(self, enabled=True):
        self.preview_calls = []
        self.video_player = SimpleNamespace(
            sub_controller=SimpleNamespace(is_enabled=enabled),
            subtitle_overlay=MagicMock(),
            player=MagicMock(position=MagicMock(return_value=1500)),
            position_changed=MagicMock(),
        )
        self.inspector_panel = SimpleNamespace(chk_preview=MagicMock())

    def set_subtitle_preview_enabled(self, enabled):
        self.preview_calls.append(enabled)
        self.video_player.sub_controller.is_enabled = enabled
        self.video_player.subtitle_overlay.setVisible(enabled)
        self.inspector_panel.chk_preview.setChecked(enabled)
        if enabled:
            self.video_player.position_changed(self.video_player.player.position())
        else:
            self.video_player.subtitle_overlay.clear_subtitle()


class TestSubtitlePreviewRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_position_changed_renders_editor_subtitle(self):
        host = QMainWindow()
        host.sub_editor = SimpleNamespace(
            all_segments=[
                {
                    "start": "00:00:01,000",
                    "end": "00:00:03,000",
                    "text": "Hello",
                    "stt": 1,
                }
            ],
            highlight_row_by_stt=MagicMock(),
            clear_highlight=MagicMock(),
        )
        player = VideoPlayerWidget(host)
        player.position_changed(1500)

        self.assertIsNotNone(player.subtitle_overlay.render_input)
        self.assertEqual(player.subtitle_overlay.render_input.text, "Hello")

    def test_turning_preview_on_refreshes_current_position(self):
        host = PreviewHost(enabled=False)
        host.video_player.position_changed = MagicMock()

        MainWindow._on_preview_toggled(host, True)

        self.assertEqual(host.preview_calls, [True])
        self.assertTrue(host.video_player.sub_controller.is_enabled)
        host.video_player.subtitle_overlay.setVisible.assert_called_once_with(True)
        host.video_player.position_changed.assert_called_once_with(1500)
        host.inspector_panel.chk_preview.setChecked.assert_called_once_with(True)

    def test_turning_preview_off_hides_and_clears_immediately(self):
        host = PreviewHost(enabled=True)

        MainWindow._on_preview_toggled(host, False)

        self.assertFalse(host.video_player.sub_controller.is_enabled)
        self.assertEqual(host.preview_calls, [False])
        self.assertFalse(host.video_player.sub_controller.is_enabled)
        host.video_player.subtitle_overlay.setVisible.assert_called_once_with(False)
        host.video_player.subtitle_overlay.clear_subtitle.assert_called_once_with()
        host.inspector_panel.chk_preview.setChecked.assert_called_once_with(False)

    def _workspace_service(self, enabled):
        host = PreviewHost(enabled=not enabled)
        host.switch_page = MagicMock()
        host.bottom_tabs = SimpleNamespace(setCurrentIndex=MagicMock())
        host.queue_mgr = SimpleNamespace(
            get_items=MagicMock(return_value=[]),
            add_video=MagicMock(),
        )
        host.on_queue_item_clicked = MagicMock()
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
        service = WorkspaceService(host, SimpleNamespace(current_project=project))
        return host, service

    def test_restore_workspace_preview_false_syncs_all_layers(self):
        host, service = self._workspace_service(False)

        service.restore_workspace()

        self.assertEqual(host.preview_calls, [False])
        self.assertFalse(host.video_player.sub_controller.is_enabled)
        host.video_player.subtitle_overlay.setVisible.assert_called_once_with(False)
        host.inspector_panel.chk_preview.setChecked.assert_called_once_with(False)

    def test_restore_workspace_preview_true_syncs_all_layers(self):
        host, service = self._workspace_service(True)

        service.restore_workspace()

        self.assertEqual(host.preview_calls, [True])
        self.assertTrue(host.video_player.sub_controller.is_enabled)
        host.video_player.subtitle_overlay.setVisible.assert_called_once_with(True)
        host.inspector_panel.chk_preview.setChecked.assert_called_once_with(True)

    def test_timeline_position_still_emits_when_preview_is_off(self):
        host = QMainWindow()
        host.sub_editor = SimpleNamespace(
            all_segments=[
                {
                    "start": "00:00:01,000",
                    "end": "00:00:03,000",
                    "text": "Hello",
                    "stt": 1,
                }
            ],
            highlight_row_by_stt=MagicMock(),
            clear_highlight=MagicMock(),
        )
        player = VideoPlayerWidget(host)
        player.sub_controller.is_enabled = False
        emitted = []
        player.timeline_position_changed.connect(emitted.append)

        player.position_changed(1500)

        self.assertEqual(emitted, [1500])


if __name__ == "__main__":
    unittest.main()
