import copy
import os
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSlider

from core.subtitle_editing.global_undo_manager import GlobalUndoManager
from core.subtitle_editing.selection_controller import SubtitleSelectionController, SelectionSource
from core.timeline.timeline_commands import ResizeEndCommand, ResizeStartCommand
from core.timeline.timeline_controller import TimelineController
from core.timeline.timeline_data_provider import TimelineDataProvider
from core.timeline.timeline_integration import TimelineVideoSync
from player.video_player import VideoPlayerWidget
from ui.timeline.subtitle_track import EditMode
from ui.timeline.timeline_widget import TimelineWidget


class MediaEngine(QObject):
    """External media backend; positions are delivered without a clock or codec."""
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playingChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.current_position = 0
        self.playing = False
        self.seeks = []

    def setAudioOutput(self, _output): pass
    def setVideoOutput(self, _output): pass
    def setSource(self, _source): pass
    def duration(self): return 10000
    def position(self): return self.current_position
    def isPlaying(self): return self.playing

    def play(self):
        self.playing = True
        self.playingChanged.emit(True)

    def pause(self):
        self.playing = False
        self.playingChanged.emit(False)

    def stop(self): self.pause()

    def setPosition(self, value):
        self.seeks.append(value)
        self.deliver(value)

    def deliver(self, value):
        self.current_position = value
        self.positionChanged.emit(value)


class LightweightPlayer(VideoPlayerWidget):
    def init_ui(self):
        # The rendering surface is irrelevant to the real player's seek/guard logic.
        self.slider_seek = QSlider(self)
        self.lbl_time = QLabel(self)
        self.btn_play = QPushButton(self)
        self.empty_state_lbl = QLabel(self)
        self.subtitle_overlay = SimpleNamespace(clear_subtitle=lambda: None)
        self.video_item = None


class TestSegmentFocus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dirty_calls = []
        self.artifact = SimpleNamespace(revision=0)
        self.project = SimpleNamespace(
            current_project=SimpleNamespace(state=SimpleNamespace(active_artifact_id="sub")),
            artifact_store=SimpleNamespace(get=lambda _id: self.artifact),
            mark_dirty=lambda: self.dirty_calls.append("dirty"),
        )
        self.rows = [
            {"id": "first", "stt": "1", "start_ms": 1000, "end_ms": 3000, "text": "one", "status": "generated"},
            {"id": "next", "stt": "2", "start_ms": 4000, "end_ms": 6000, "text": "two", "status": "generated"},
        ]
        self.provider = TimelineDataProvider()
        self.provider.load_runtime_data(self.rows, 10000)
        self.timeline = TimelineWidget()
        self.timeline.load_project_data(10000, self.provider.get_all_segments())
        self.selection = SubtitleSelectionController()
        self.undo = GlobalUndoManager()
        self.controller = TimelineController(
            self.project, self.timeline, self.provider, self.undo, self.selection
        )
        self.undo.state_changed.connect(self.controller._refresh_ui)
        with patch("player.video_player.QMediaPlayer", MediaEngine):
            self.player = LightweightPlayer()
        self.sync = TimelineVideoSync(self.player, self.timeline, self.controller.state_manager)
        self.selection.select(0, "first", SelectionSource.EDITOR)

    def tearDown(self):
        self.undo.undo_stack.cleanChanged.disconnect()
        self.player.cleanup()
        self.player.player.playingChanged.disconnect()
        self.player.player.positionChanged.disconnect()
        self.player.close()
        self.timeline.close()
        self.player.deleteLater()
        self.timeline.deleteLater()

    def play_segment(self):
        button = getattr(self.timeline.container, "play_segment_button", None)
        self.assertIsNotNone(button, "selected subtitle must offer Play Segment")
        self.assertTrue(button.isEnabled())
        button.click()

    def test_single_selection_displays_current_range_without_dirty_or_undo(self):
        self.assertEqual(self.timeline.container.start_range_edit.text(), "00:00:01,000")
        self.assertEqual(self.timeline.container.end_range_edit.text(), "00:00:03,000")
        self.assertEqual(self.timeline.container.range_duration.text(), "00:00:02,000")
        self.assertTrue(self.timeline.container.start_range_edit.isReadOnly())
        self.assertEqual(self.timeline.container.waveform._selected_range_ms, (1000, 3000))
        self.assertEqual(self.dirty_calls, [])
        self.assertEqual(self.undo.undo_stack.count(), 0)

    def test_gap_and_manual_range_clear_canonical_subtitle_focus(self):
        for action in (
            lambda: self.timeline.select_gap(self.timeline.container.track.gaps[1]),
            lambda: self.timeline.set_generation_range(3200, 3700),
        ):
            self.selection.select(0, "first", SelectionSource.EDITOR)
            action()
            self.assertIsNone(self.selection.selected_segment_id)
            self.assertEqual(self.timeline.container.track.selected_ids, set())
            self.assertIsNotNone(self.timeline.generation_range)
            self.assertFalse(self.timeline.container.start_range_edit.isReadOnly())

    def test_selecting_subtitle_clears_generation_range(self):
        self.timeline.set_generation_range(3200, 3700)
        self.selection.select(0, "first", SelectionSource.EDITOR)
        self.assertIsNone(self.timeline.generation_range)
        self.assertEqual(self.timeline.container.waveform._selected_range_ms, (1000, 3000))
        self.assertEqual(self.timeline.container.start_range_edit.text(), "00:00:01,000")

    def test_ctrl_multi_selection_disables_single_focus_and_preserves_multi_selection(self):
        QTest.mouseClick(self.timeline.container.track, Qt.LeftButton, Qt.ControlModifier, QPoint(500, 30))
        self.assertEqual(self.timeline.container.track.selected_ids, {"first", "next"})
        self.assertIsNone(self.selection.selected_segment_id)
        self.assertIsNone(self.timeline.container.waveform._selected_range_ms)
        button = getattr(self.timeline.container, "play_segment_button", None)
        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())

    def test_empty_selection_disables_focus(self):
        self.selection.clear_selection()
        self.assertIsNone(self.timeline.container.waveform._selected_range_ms)
        button = getattr(self.timeline.container, "play_segment_button", None)
        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())

    def test_play_segment_seeks_exact_start_and_pauses_at_or_after_end(self):
        for end_position in (3000, 3100):
            self.play_segment()
            self.assertEqual(self.player.player.seeks[-1], 1000)
            self.assertTrue(self.player.player.isPlaying())
            self.player.player.deliver(2999)
            self.assertTrue(self.player.player.isPlaying())
            self.player.player.deliver(end_position)
            self.assertFalse(self.player.player.isPlaying())
            self.player.toggle_playback()
            self.player.player.deliver(5000)
            self.assertTrue(self.player.player.isPlaying())
            self.player.player.pause()

    def test_inside_seek_keeps_guard_and_outside_seek_clears_it(self):
        self.play_segment()
        self.player.set_position(2000)
        self.player.player.deliver(3000)
        self.assertFalse(self.player.player.isPlaying())
        self.play_segment()
        self.player.set_position(3500)
        self.player.player.deliver(5000)
        self.assertTrue(self.player.player.isPlaying())

    def test_user_pause_does_not_leave_guard_for_normal_playback(self):
        self.play_segment()
        self.player.player.pause()
        self.player.toggle_playback()
        self.player.player.deliver(5000)
        self.assertTrue(self.player.player.isPlaying())

    def test_selection_change_terminates_focused_playback(self):
        self.play_segment()
        self.selection.select(1, "next", SelectionSource.EDITOR)
        self.assertFalse(self.player.player.isPlaying())
        self.player.toggle_playback()
        self.player.player.deliver(7000)
        self.assertTrue(self.player.player.isPlaying())

    def test_reload_clear_and_media_cleanup_do_not_leave_playback_guard(self):
        for reset in (self.timeline.clear, lambda: self.timeline.load_project_data(10000, []), self.player.cleanup):
            self.timeline.load_project_data(10000, self.provider.get_all_segments())
            self.controller.sync_selection(0, "first")
            self.play_segment()
            reset()
            self.player.toggle_playback()
            self.player.player.deliver(5000)
            self.assertTrue(self.player.player.isPlaying())
            self.player.player.pause()

    def test_trim_extend_use_one_command_and_refresh_focus_after_undo_redo(self):
        for mode, delta, expected in (
            (EditMode.RESIZE_LEFT, 500, (1500, 3000)),
            (EditMode.RESIZE_LEFT, -500, (500, 3000)),
            (EditMode.RESIZE_RIGHT, -500, (1000, 2500)),
            (EditMode.RESIZE_RIGHT, 1500, (1000, 4500)),
        ):
            with self.subTest(mode=mode, delta=delta):
                neighbor = copy.deepcopy(self.provider.get_segment("next").get_raw_dict())
                self.controller.handle_edit_commit("first", mode, delta)
                self.assertEqual(self.timeline.container.waveform._selected_range_ms, expected)
                self.assertEqual(self.selection.selected_segment_id, "first")
                self.assertEqual(self.undo.undo_stack.count(), 1)
                self.assertEqual(self.dirty_calls, ["dirty"])
                self.assertEqual(self.provider.get_segment("next").get_raw_dict(), neighbor)
                self.controller.handle_undo()
                self.assertEqual(self.timeline.container.waveform._selected_range_ms, (1000, 3000))
                self.controller.handle_redo()
                self.assertEqual(self.timeline.container.waveform._selected_range_ms, expected)
                self.controller.handle_undo()
                self.undo.clear()
                self.dirty_calls.clear()

    def test_resize_rejects_media_bounds_and_minimum_duration(self):
        for command in (
            ResizeStartCommand(self.project, self.provider, "first", -1001),
            ResizeStartCommand(self.project, self.provider, "first", 1901),
            ResizeEndCommand(self.project, self.provider, "first", -1901),
            ResizeEndCommand(self.project, self.provider, "first", 7001),
        ):
            self.assertFalse(command.can_execute())

    def test_begin_resize_pauses_focused_playback_before_any_mutation(self):
        self.play_segment()
        QTest.mousePress(self.timeline.container.track, Qt.LeftButton, Qt.NoModifier, QPoint(100, 30))
        self.assertFalse(self.player.player.isPlaying())
        self.assertEqual(self.provider.get_segment("first").start_ms, 1000)
        self.assertEqual(self.dirty_calls, [])
        QTest.mouseRelease(self.timeline.container.track, Qt.LeftButton, Qt.NoModifier, QPoint(100, 30))

    def test_trim_recomputes_gap_and_play_uses_edited_bounds(self):
        self.controller.handle_edit_commit("first", EditMode.RESIZE_LEFT, 500)
        self.assertEqual([(g.start_ms, g.end_ms) for g in self.timeline.container.track.gaps], [(0, 1500), (3000, 4000), (6000, 10000)])
        self.play_segment()
        self.assertEqual(self.player.player.seeks[-1], 1500)
        self.player.player.deliver(3000)
        self.assertFalse(self.player.player.isPlaying())

    def test_delete_clears_selection_and_playback(self):
        self.play_segment()
        self.controller._trigger_delete()
        self.assertIsNone(self.selection.selected_segment_id)
        self.assertIsNone(self.timeline.container.waveform._selected_range_ms)
        self.assertIsNone(self.provider.get_segment("first"))
        self.assertFalse(self.player.player.isPlaying())

    def test_generated_subtitle_artifact_can_be_resized_without_timing_artifact(self):
        self.project.current_project.state.active_artifact_id = None
        self.project.current_project.state.subtitle_artifact_id = "sub"
        self.controller.handle_edit_commit("first", EditMode.RESIZE_LEFT, 500)
        self.assertEqual(self.provider.get_segment("first").start_ms, 1500)

    def test_timeline_seek_inside_current_segment_keeps_playback_guard(self):
        self.play_segment()
        self.controller._do_seek(self.timeline.container.track.pixels_per_second * 2)
        self.assertTrue(self.player.player.isPlaying())
        self.player.player.deliver(3000)
        self.assertFalse(self.player.player.isPlaying())

    def test_edge_drag_preview_is_transient_and_release_commits_once(self):
        track = self.timeline.container.track
        track.snap_enabled = False
        start_x = int(track.pixels_per_second)
        end_x = start_x + int(track.pixels_per_second / 2)
        QTest.mousePress(track, Qt.LeftButton, Qt.NoModifier, QPoint(start_x, 30))
        move = QMouseEvent(QEvent.MouseMove, QPointF(end_x, 30), QPointF(end_x, 30), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        self.app.sendEvent(track, move)
        self.assertEqual(self.provider.get_segment("first").start_ms, 1000)
        self.assertEqual(self.undo.undo_stack.count(), 0)
        self.assertEqual(self.dirty_calls, [])
        QTest.mouseRelease(track, Qt.LeftButton, Qt.NoModifier, QPoint(end_x, 30))
        self.assertEqual(self.provider.get_segment("first").start_ms, 1500)
        self.assertEqual(self.undo.undo_stack.count(), 1)
        self.assertEqual(self.dirty_calls, ["dirty"])
        self.assertEqual(self.selection.selected_segment_id, "first")

    def test_extend_shrinks_derived_gap_without_asr_or_neighbor_mutation(self):
        neighbor = copy.deepcopy(self.provider.get_segment("next").get_raw_dict())
        self.controller.handle_edit_commit("first", EditMode.RESIZE_RIGHT, 500)
        self.assertEqual([(g.start_ms, g.end_ms) for g in self.timeline.container.track.gaps], [(0, 1000), (3500, 4000), (6000, 10000)])
        self.assertEqual(self.provider.get_segment("next").get_raw_dict(), neighbor)
        self.assertEqual(self.timeline.container.end_range_edit.text(), "00:00:03,500")
        self.assertEqual(self.timeline.container.range_duration.text(), "00:00:02,500")

    def test_split_follows_existing_retained_identity_and_merge_selects_result(self):
        self.timeline.container.track.playhead_ms = 2000
        self.controller._trigger_split()
        self.assertEqual(self.selection.selected_segment_id, "first")
        self.assertEqual(self.timeline.container.waveform._selected_range_ms, (1000, 2000))
        children = [s.segment_id for s in self.provider.get_all_segments() if s.start_ms < 3000]
        self.timeline.container.track.set_selection(set(children))
        self.controller._on_track_selection_changed()
        self.controller._trigger_merge()
        segment = self.provider.get_segment(self.selection.selected_segment_id)
        self.assertIsNotNone(segment)
        self.assertEqual(self.timeline.container.waveform._selected_range_ms, (1000, 3000))

    def test_media_change_cancels_guard_and_missing_selection_never_falls_back_to_another_row(self):
        self.play_segment()
        with tempfile.NamedTemporaryFile() as media:
            self.player.load_video(media.name)
        self.assertFalse(self.player.player.isPlaying())
        self.player.toggle_playback()
        self.player.player.deliver(5000)
        self.assertTrue(self.player.player.isPlaying())
        self.controller.sync_selection(0, "deleted-id")
        self.assertIsNone(self.timeline.focused_segment)
        self.assertFalse(self.timeline.container.play_segment_button.isEnabled())


class TestSegmentFocusCanonicalIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from core.artifacts.artifact_store import ArtifactStore
        from core.services.project_service import ProjectService
        from core.subtitle_generation.subtitle_artifact_service import SubtitleArtifactService
        from ui.Gui import MainWindow

        self.temp = tempfile.TemporaryDirectory()
        media_path = os.path.join(self.temp.name, "media.mp4")
        with open(media_path, "wb") as handle:
            handle.write(b"test media")
        self.service = ProjectService(ArtifactStore())
        self.service.create_project(os.path.join(self.temp.name, "project.ai-subtitle"), "project", media_path)
        self.artifact_service = SubtitleArtifactService(self.service)
        self.artifact = self.artifact_service.create_artifact_with_data({"version": 1, "segments": [
            {"id": "first", "stt": "1", "start_ms": 1000, "end_ms": 3000, "text": "one", "status": "generated", "words": [{"word": "one", "start": 1.0, "end": 3.0}], "metadata": {"source": "ASR"}},
        ]})
        self.window = MainWindow(project_service=self.service)
        self.window.sub_editor.all_segments = self.artifact_service.load_data(self.artifact.path)["segments"]
        self.window.timeline_widget.load_project_data(10000, [])
        self.window.timeline_controller.sync_from_editor_segments(self.window.sub_editor.all_segments)
        self.window.selection_controller.select(0, "first", SelectionSource.EDITOR)
        self.window.undo_manager.clear()
        self.window.revision_tracker.reset_for_new_document()

    def tearDown(self):
        self.window.undo_manager.undo_stack.cleanChanged.disconnect()
        self.service.close_project()
        self.window.undo_manager.clear()
        self.window.revision_tracker.reset_for_new_document()
        self.window.close()
        self.window.deleteLater()
        self.temp.cleanup()

    def test_timeline_resize_is_one_revision_and_one_dirty_call_in_real_window(self):
        self.service.current_project.state.active_artifact_id = self.artifact.artifact_id
        with patch.object(self.service, "mark_dirty", wraps=self.service.mark_dirty) as dirty:
            self.window.timeline_controller.handle_edit_commit("first", EditMode.RESIZE_LEFT, 500)
        self.assertEqual(dirty.call_count, 1)
        self.assertEqual(self.window.revision_tracker.edit_revision, 1)
        self.assertEqual(self.window.undo_manager.undo_stack.count(), 1)
        self.assertEqual(self.window.sub_editor.inp_start.text(), "00:00:01,500")
        self.assertEqual(self.window.timeline_widget.container.waveform._selected_range_ms, (1500, 3000))

    def test_save_reload_preserves_generated_segment_timing_and_identity_without_focus_data(self):
        from core.artifacts.artifact_store import ArtifactStore
        from core.services.project_service import ProjectService

        self.window.timeline_controller.handle_edit_commit("first", EditMode.RESIZE_RIGHT, 500)
        self.assertTrue(self.window._save_current_project(notify_user=False))
        reopened = ProjectService(ArtifactStore())
        reopened.open_project(self.service.project_dir)
        artifact = reopened.artifact_store.get(reopened.current_project.state.subtitle_artifact_id)
        with open(artifact.path, encoding="utf-8") as handle:
            rows = json.load(handle)["segments"]
        self.assertEqual((rows[0]["start_ms"], rows[0]["end_ms"], rows[0]["id"], rows[0]["text"]), (1000, 3500, "first", "one"))
        self.assertFalse(any("focus" in key for key in rows[0]))
        self.assertEqual(rows[0]["metadata"], {"source": "ASR"})
        self.assertEqual(rows[0]["words"], [{"word": "one", "start": 1.0, "end": 3.0}])
        self.window.timeline_widget.clear()
        self.assertFalse(self.window.timeline_widget.container.play_segment_button.isEnabled())

    def test_full_generation_reload_keeps_canonical_identity_and_metadata_for_timing_edit(self):
        shadow = self.window._on_generation_batch_sync()
        self.window._load_generated_subtitles_into_ui(shadow)
        row = self.window.sub_editor.all_segments[0]
        self.assertEqual(row["id"], "first")
        self.assertEqual(row["metadata"], {"source": "ASR"})


if __name__ == "__main__":
    unittest.main()
