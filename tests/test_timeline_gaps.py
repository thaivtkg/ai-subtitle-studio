import os
import unittest
from copy import deepcopy
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.timeline.gaps import find_timeline_gaps
from core.timeline.timeline_controller import TimelineController
from core.timeline.timeline_data_provider import TimelineDataProvider
from core.timeline.timeline_undo_manager import UndoRedoManager
from core.subtitle_editing.selection_controller import SubtitleSelectionController
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ui.timeline.timeline_widget import TimelineWidget


def segment(segment_id, start_ms, end_ms, text=""):
    return SimpleNamespace(segment_id=segment_id, start_ms=start_ms, end_ms=end_ms, text=text)


class TestTimelineGaps(unittest.TestCase):
    def test_empty_media_has_no_gaps(self):
        self.assertEqual(find_timeline_gaps(0, []), [])
        self.assertEqual(find_timeline_gaps(-1, []), [])

    def test_media_without_subtitles_is_one_gap(self):
        self.assertEqual(
            [(g.start_ms, g.end_ms, g.duration_ms, g.previous_id, g.next_id)
             for g in find_timeline_gaps(10000, [])],
            [(0, 10000, 10000, None, None)],
        )

    def test_first_internal_and_last_gaps_ignore_text(self):
        gaps = find_timeline_gaps(10000, [segment("a", 1000, 3000), segment("b", 5000, 8000, "hi")])
        self.assertEqual(
            [(g.start_ms, g.end_ms, g.previous_id, g.next_id) for g in gaps],
            [(0, 1000, None, "a"), (3000, 5000, "a", "b"), (8000, 10000, "b", None)],
        )

    def test_overlap_union_uses_actual_nearest_boundary_segment(self):
        gaps = find_timeline_gaps(10000, [
            segment("long", 1000, 6000), segment("inside", 2000, 3000),
            segment("next", 7000, 8000),
        ])
        self.assertEqual((gaps[1].start_ms, gaps[1].end_ms, gaps[1].previous_id, gaps[1].next_id),
                         (6000, 7000, "long", "next"))

    def test_touching_ranges_and_one_ms_gap(self):
        gaps = find_timeline_gaps(2001, [segment("a", 0, 1000), segment("b", 1000, 2000)])
        self.assertEqual([(g.start_ms, g.end_ms) for g in gaps], [(2000, 2001)])

    def test_invalid_and_out_of_bounds_ranges_are_clamped(self):
        gaps = find_timeline_gaps(1000, [
            segment("before", -100, 100), segment("zero", 300, 300),
            segment("after", 900, 1200), segment("outside", 1100, 1300),
        ])
        self.assertEqual([(g.start_ms, g.end_ms, g.previous_id, g.next_id) for g in gaps],
                         [(100, 900, "before", "after")])

    def test_malformed_timing_does_not_block_valid_coverage(self):
        gaps = find_timeline_gaps(1000, [
            segment("bad", None, 300), segment("bad-text", "x", 500),
            segment("valid", 300, 700),
        ])
        self.assertEqual([(g.start_ms, g.end_ms) for g in gaps], [(0, 300), (700, 1000)])


class TestTimelineGapSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_click_gap_shows_details_and_waveform_range_without_mutation(self):
        raw = [segment("a", 0, 1000, "")]
        timeline = TimelineWidget()
        timeline.load_project_data(3000, raw)
        track = timeline.container.track
        track.resize(300, 60)
        QTest.mouseClick(track, Qt.LeftButton, pos=track.rect().center())
        self.assertEqual((timeline.selected_gap.start_ms, timeline.selected_gap.end_ms), (1000, 3000))
        self.assertEqual(timeline.container.waveform._selected_range_ms, (1000, 3000))
        self.assertEqual(timeline.container.start_range_edit.text(), "00:00:01,000")
        self.assertEqual(timeline.container.end_range_edit.text(), "00:00:03,000")
        self.assertEqual(timeline.container.range_duration.text(), "00:00:02,000")
        self.assertTrue(timeline.container.generate_gap_button.isEnabled())
        self.assertEqual((raw[0].start_ms, raw[0].end_ms), (0, 1000))

    def test_reload_or_subtitle_click_clears_selected_gap(self):
        timeline = TimelineWidget()
        timeline.load_project_data(3000, [segment("a", 0, 1000)])
        track = timeline.container.track
        track.resize(300, 60)
        QTest.mouseClick(track, Qt.LeftButton, pos=track.rect().center())
        self.assertIsNotNone(timeline.selected_gap)
        QTest.mouseClick(track, Qt.LeftButton, pos=QPoint(50, 30))
        self.assertIsNone(timeline.selected_gap)
        QTest.mouseClick(track, Qt.LeftButton, pos=track.rect().center())
        timeline.load_project_data(3000, [segment("a", 0, 3000)])
        self.assertIsNone(timeline.selected_gap)
        self.assertIsNone(timeline.container.waveform._selected_range_ms)

    def test_one_ms_gap_marker_is_clickable_without_changing_timing(self):
        timeline = TimelineWidget()
        timeline.load_project_data(2001, [segment("a", 0, 2000)])
        track = timeline.container.track
        track.resize(201, 60)
        QTest.mouseClick(track, Qt.LeftButton, pos=QPoint(200, 2))
        self.assertEqual((timeline.selected_gap.start_ms, timeline.selected_gap.end_ms), (2000, 2001))

    def test_gap_details_remain_visible_at_compact_timeline_height(self):
        timeline = TimelineWidget()
        timeline.setMinimumHeight(160)
        timeline.resize(800, 160)
        timeline.load_project_data(3000, [])
        timeline.show()
        timeline.select_gap(timeline.container.track.gaps[0])
        self.app.processEvents()
        self.assertFalse(timeline.container.gap_row.visibleRegion().isEmpty())

    def test_gap_selection_clears_segment_selection_without_dirty_or_undo(self):
        timeline = TimelineWidget()
        provider = TimelineDataProvider()
        raw = [{"id": "a", "start_ms": 0, "end_ms": 1000, "text": ""}]
        provider.load_runtime_data(raw, 3000)
        before_selection = deepcopy(raw)
        timeline.load_project_data(3000, provider.get_all_segments())
        selection = SubtitleSelectionController()
        undo = UndoRedoManager()
        project = SimpleNamespace(mark_dirty=lambda: self.fail("gap selection dirtied project"))
        controller = TimelineController(project, timeline, provider, undo_manager=undo, selection_controller=selection)
        selection.select(0, "a")

        timeline.select_gap(timeline.container.track.gaps[0])

        self.assertIsNone(selection.selected_segment_id)
        self.assertEqual(timeline.container.track.selected_ids, set())
        self.assertEqual(timeline.container.waveform._selected_range_ms, (1000, 3000))
        self.assertEqual(undo._undo_stack, [])
        self.assertEqual(raw, before_selection)


if __name__ == "__main__":
    unittest.main()
