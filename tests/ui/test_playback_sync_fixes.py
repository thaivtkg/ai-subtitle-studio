import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.subtitle_editing.selection_controller import (
    SelectionSource,
    SubtitleSelectionController,
)
from core.timeline.timeline_controller import TimelineController
from core.timeline.timeline_data_provider import TimelineDataProvider
from player.video_player import VideoPlayerWidget
from ui.SubEditor import SubtitleEditorWidget
from ui.timeline.timeline_widget import TimelineWidget


_app = QApplication.instance() or QApplication([])


class TestPlaybackSyncFixes(unittest.TestCase):
    def setUp(self):
        self.sub_editor = SubtitleEditorWidget()
        self.sub_editor.all_segments = [
            {"stt": 1, "id": "seg_1", "start": "00:00:00,000", "end": "00:00:05,000", "start_ms": 0, "end_ms": 5000, "text": "First"},
            {"stt": 2, "id": "seg_2", "start": "00:00:10,000", "end": "00:00:16,000", "start_ms": 10000, "end_ms": 16000, "text": "Second"},
            {"stt": 3, "id": "seg_3", "start": "00:00:20,000", "end": "00:00:25,000", "start_ms": 20000, "end_ms": 25000, "text": "Third"},
        ]
        self.sub_editor._visible_source_indices = [0, 1, 2]
        self.sub_editor.render_page()

    def tearDown(self):
        self.sub_editor.close()
        self.sub_editor.deleteLater()

    def test_tc_sync_01_highlight_row_by_stt_updates_current_editor_and_selection(self):
        """TC-SYNC-01: highlight_row_by_stt updates current subtitle editor and notifies selection_controller."""
        selection_ctrl = MagicMock(spec=SubtitleSelectionController)
        self.sub_editor.selection_controller = selection_ctrl

        self.sub_editor.highlight_row_by_stt(2)

        self.assertEqual(self.sub_editor.current_index, 1)
        self.assertIn("#2", self.sub_editor.current_editor.lbl_title.text())
        selection_ctrl.select.assert_called_once_with(1, "seg_2", SelectionSource.PLAYBACK)

        # Highlight next sentence #3
        selection_ctrl.reset_mock()
        self.sub_editor.highlight_row_by_stt(3)
        self.assertEqual(self.sub_editor.current_index, 2)
        self.assertIn("#3", self.sub_editor.current_editor.lbl_title.text())
        selection_ctrl.select.assert_called_once_with(2, "seg_3", SelectionSource.PLAYBACK)

    def test_tc_sync_02_video_player_segment_bounds_release_and_global_time(self):
        """TC-SYNC-02: toggle_playback and position_changed release _segment_bounds when leaving segment."""
        player = VideoPlayerWidget()
        try:
            player._segment_bounds = (10000, 16000)
            player._segment_playback_active = False

            # toggle_playback releases segment focus
            player.toggle_playback()
            self.assertIsNone(player._segment_bounds)

            # position_changed outside bounds releases _segment_bounds
            player._segment_bounds = (10000, 16000)
            player._segment_playback_active = False
            player.position_changed(20000)
            self.assertIsNone(player._segment_bounds)
        finally:
            player.close()
            player.deleteLater()

    def test_tc_play_01_global_selection_ignores_playback_source(self):
        """TC-PLAY-01: _on_global_selection_changed ignores PLAYBACK source to prevent pausing video."""
        from ui.Gui import MainWindow
        win = MainWindow.__new__(MainWindow)
        win.sub_editor = SimpleNamespace(
            all_segments=[
                {"start": "00:00:10,000", "end": "00:00:16,000", "start_ms": 10000, "end_ms": 16000, "text": "Sub"}
            ]
        )
        focused_calls = []
        win._on_segment_focused = lambda s, e: focused_calls.append((s, e))

        # PLAYBACK source must be ignored
        MainWindow._on_global_selection_changed(win, 0, "seg_id", SelectionSource.PLAYBACK)
        self.assertEqual(len(focused_calls), 0)

        # EDITOR source must trigger segment preview
        MainWindow._on_global_selection_changed(win, 0, "seg_id", SelectionSource.EDITOR)
        self.assertEqual(len(focused_calls), 1)
        self.assertEqual(focused_calls[0], (10000, 16000))

    def test_tc_wmv_format_detection(self):
        """TC-WMV-01: Detects WMV / ASF extension and binary header."""
        player = VideoPlayerWidget()
        try:
            self.assertTrue(player._is_legacy_wmv_format("test.wmv"))
            self.assertTrue(player._is_legacy_wmv_format("video.asf"))
            self.assertFalse(player._is_legacy_wmv_format("video.mp4"))

            # Test ASF binary header even if named .mp4
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c" + b"extra_bytes")
                temp_path = f.name
            try:
                self.assertTrue(player._is_legacy_wmv_format(temp_path))
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        finally:
            player.close()
            player.deleteLater()

