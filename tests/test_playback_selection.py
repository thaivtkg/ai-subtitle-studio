import unittest
from unittest.mock import Mock

from core.subtitle_controller import SubtitleController
from player.video_player import VideoPlayerWidget


class TestPlaybackSubtitleTransitions(unittest.TestCase):
    def test_live_editor_data_emits_when_playback_enters_next_subtitle(self):
        controller = SubtitleController()
        changes = []
        controller.subtitle_changed.connect(lambda *args: changes.append(args))

        controller.update_live_data([
            (1000, 2000, "first", 1),
            (2000, 3000, "second", 2),
        ])
        controller.sync_position(2500)

        self.assertEqual(changes, [(2, 2000, "second")])

    def test_paused_seek_syncs_subtitle_controller_before_ui_refresh(self):
        widget = VideoPlayerWidget.__new__(VideoPlayerWidget)
        widget.player = Mock()
        widget.player.isPlaying.return_value = False
        widget.sub_controller = Mock()
        widget.position_changed = Mock()

        widget.set_position(6500)

        widget.sub_controller.sync_position.assert_called_once_with(6500)
        widget.position_changed.assert_called_once_with(6500)


if __name__ == "__main__":
    unittest.main()
