import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from ui.SubEditor import SubtitleEditorWidget
from ui.pages.settings_page import SettingsCenterPage
from core.subtitle_editing.global_undo_manager import GlobalUndoManager


class TestTimingNudgeAndSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.undo_mgr = GlobalUndoManager()
        self.editor = SubtitleEditorWidget()
        self.editor.undo_manager = self.undo_mgr
        self.editor._load_segments([
            {"stt": "1", "start": "00:00:10,000", "end": "00:00:15,000", "text": "Segment 1"},
            {"stt": "2", "start": "00:00:16,000", "end": "00:00:19,000", "text": "Segment 2"},
        ], "test.srt")

    def test_settings_tabs_and_styling(self):
        page = SettingsCenterPage()
        tab_names = [page.nav_list.item(i).text() for i in range(page.nav_list.count())]
        self.assertEqual(tab_names, ["🎨 Kiểu phụ đề", "🎬 Hardsub FFmpeg", "⚙️ Chung & Giao diện"])
        self.assertNotIn("Whisper AI", tab_names)
        self.assertEqual(page.stack.count(), 3)
        self.assertEqual(page.nav_list.objectName(), "SettingsNav")
        self.assertIn("border: none", page.nav_list.styleSheet())
        self.assertIn("outline: none", page.nav_list.styleSheet())

    def test_nudge_both(self):
        self.editor.select_segment(1)
        # Nudge +100ms
        self.editor.nudge_selected_segment(100, target="both")
        seg = self.editor.all_segments[1]
        self.assertEqual(seg["start"], "00:00:16,100")
        self.assertEqual(seg["end"], "00:00:19,100")

        # Nudge -1000ms (-1s)
        self.editor.nudge_selected_segment(-1000, target="both")
        seg = self.editor.all_segments[1]
        self.assertEqual(seg["start"], "00:00:15,100")
        self.assertEqual(seg["end"], "00:00:18,100")

        # Undo
        self.undo_mgr.undo()
        seg = self.editor.all_segments[1]
        self.assertEqual(seg["start"], "00:00:16,100")
        self.assertEqual(seg["end"], "00:00:19,100")

    def test_nudge_start_only(self):
        self.editor.select_segment(0)
        self.editor.nudge_selected_segment(-500, target="start")
        seg = self.editor.all_segments[0]
        self.assertEqual(seg["start"], "00:00:09,500")
        self.assertEqual(seg["end"], "00:00:15,000")

    def test_nudge_end_only(self):
        self.editor.select_segment(0)
        self.editor.nudge_selected_segment(500, target="end")
        seg = self.editor.all_segments[0]
        self.assertEqual(seg["start"], "00:00:10,000")
        self.assertEqual(seg["end"], "00:00:15,500")

    def test_nudge_updates_start_ms_and_wrapper(self):
        from core.timeline.timeline_data_provider import TimelineDataProvider, TimelineSegmentWrapper
        provider = TimelineDataProvider()
        provider.load_runtime_data(self.editor.all_segments, 30000)
        wrapper = provider._segments[1]
        self.assertEqual(wrapper.start_ms, 16000)
        self.assertEqual(wrapper.end_ms, 19000)

        # Nudge segment 1 by +200ms
        self.editor.select_segment(1)
        self.editor.nudge_selected_segment(200, target="both")

        # Check raw segment dict
        seg = self.editor.all_segments[1]
        self.assertEqual(seg["start_ms"], 16200)
        self.assertEqual(seg["end_ms"], 19200)

        # Check wrapper dynamic sync
        self.assertEqual(wrapper.start_ms, 16200)
        self.assertEqual(wrapper.end_ms, 19200)

    def test_table_selection_retained_after_nudge(self):
        self.editor.select_segment(1)
        self.assertEqual(self.editor.table.currentRow(), 1)

        # Nudge and trigger page render
        self.editor.nudge_selected_segment(100, target="both")
        self.editor.render_page()

        # Selection should still be on row 1
        self.assertEqual(self.editor.table.currentRow(), 1)
        self.assertEqual(self.editor.current_index, 1)

    def test_ripple_shift_on_nudge_and_undo(self):
        self.editor._load_segments([
            {"stt": "1", "start": "00:00:10,000", "end": "00:00:15,000", "text": "Segment 1"},
            {"stt": "2", "start": "00:00:16,000", "end": "00:00:19,000", "text": "Segment 2"},
            {"stt": "3", "start": "00:00:20,000", "end": "00:00:25,000", "text": "Segment 3"},
        ], "test.srt")
        self.editor.ripple_shift_enabled = True
        self.editor.select_segment(0)

        # Nudge +1s on entire segment 0
        self.editor.nudge_selected_segment(1000, target="both")
        self.assertEqual(self.editor.all_segments[0]["start"], "00:00:11,000")
        self.assertEqual(self.editor.all_segments[0]["end"], "00:00:16,000")
        # Segments 1 and 2 must have rippled by +1s
        self.assertEqual(self.editor.all_segments[1]["start"], "00:00:17,000")
        self.assertEqual(self.editor.all_segments[1]["end"], "00:00:20,000")
        self.assertEqual(self.editor.all_segments[2]["start"], "00:00:21,000")
        self.assertEqual(self.editor.all_segments[2]["end"], "00:00:26,000")

        # Atomic undo restores all 3
        self.undo_mgr.undo()
        self.assertEqual(self.editor.all_segments[0]["start"], "00:00:10,000")
        self.assertEqual(self.editor.all_segments[0]["end"], "00:00:15,000")
        self.assertEqual(self.editor.all_segments[1]["start"], "00:00:16,000")
        self.assertEqual(self.editor.all_segments[1]["end"], "00:00:19,000")
        self.assertEqual(self.editor.all_segments[2]["start"], "00:00:20,000")
        self.assertEqual(self.editor.all_segments[2]["end"], "00:00:25,000")

    def test_ripple_shift_disabled_on_nudge(self):
        self.editor._load_segments([
            {"stt": "1", "start": "00:00:10,000", "end": "00:00:15,000", "text": "Segment 1"},
            {"stt": "2", "start": "00:00:16,000", "end": "00:00:19,000", "text": "Segment 2"},
        ], "test.srt")
        self.editor.ripple_shift_enabled = False
        self.editor.select_segment(0)

        self.editor.nudge_selected_segment(1000, target="both")
        self.assertEqual(self.editor.all_segments[0]["start"], "00:00:11,000")
        self.assertEqual(self.editor.all_segments[0]["end"], "00:00:16,000")
        # Segment 2 unchanged when ripple is disabled
        self.assertEqual(self.editor.all_segments[1]["start"], "00:00:16,000")
        self.assertEqual(self.editor.all_segments[1]["end"], "00:00:19,000")

    def test_ripple_shift_on_manual_edit(self):
        self.editor._load_segments([
            {"stt": "1", "start": "00:00:10,000", "end": "00:00:15,000", "text": "Segment 1"},
            {"stt": "2", "start": "00:00:16,000", "end": "00:00:19,000", "text": "Segment 2"},
        ], "test.srt")
        self.editor.ripple_shift_enabled = True
        self.editor.select_segment(0)

        # Manually increase end from 15s to 17s (+2000ms)
        self.editor._apply_current_editor({
            "start": "00:00:10,000",
            "end": "00:00:17,000",
            "text": "Segment 1",
        })
        self.assertEqual(self.editor.all_segments[0]["end"], "00:00:17,000")
        # Segment 2 rippled by +2000ms
        self.assertEqual(self.editor.all_segments[1]["start"], "00:00:18,000")
        self.assertEqual(self.editor.all_segments[1]["end"], "00:00:21,000")

    def test_auto_range_filter_and_buttons_hidden(self):
        # Buttons are hidden from UI
        self.assertTrue(self.editor.btn_apply_range.isHidden())
        self.assertTrue(self.editor.btn_clear_range.isHidden())

        # Typing valid end minute auto-applies filter (defaulting start to 0)
        self.editor.range_end_input.setText("1")
        self.assertEqual(self.editor._active_time_range_ms, (0, 60000))

        # Clearing both inputs auto-clears filter
        self.editor.range_end_input.setText("")
        self.editor.range_start_input.setText("")
        self.assertIsNone(self.editor._active_time_range_ms)


if __name__ == "__main__":
    unittest.main()
