import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import numpy as np
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from ui.timeline.waveform_view import WaveformView
    from core.subtitle_editing.selection_controller import (
        SelectionSource,
        SubtitleSelectionController,
    )
    from core.timeline.timeline_data_provider import TimelineDataProvider
    from core.timeline.timeline_controller import TimelineController
    from ui.theme import Theme
    from ui.SubEditor import SubtitleEditorWidget
    from ui.timeline.timeline_widget import TimelineWidget
except (ImportError, ModuleNotFoundError):
    np = None
    QColor = None
    QImage = None
    QApplication = None
    WaveformView = None
    SelectionSource = None
    SubtitleSelectionController = None
    TimelineDataProvider = None
    TimelineController = None
    Theme = None
    SubtitleEditorWidget = None
    TimelineWidget = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestWaveformSelectionFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.waveform = WaveformView()
        self.waveform.resize(1000, 100)
        self.waveform.set_data(np.zeros((1000, 2)), 10000)

    def test_selected_range_is_stored_in_milliseconds(self):
        self.waveform.set_selected_range(1000, 2500)

        self.assertEqual(self.waveform._selected_range_ms, (1000, 2500))

    def test_selected_range_geometry_uses_default_zoom(self):
        self.waveform.set_selected_range(1000, 2500)

        rect = self.waveform._selected_range_rect()

        self.assertEqual(self.waveform._ms_to_x(1000), 100)
        self.assertEqual(self.waveform._ms_to_x(2500), 250)
        self.assertEqual(rect.left(), 100)
        self.assertEqual(rect.width(), 150)

    def test_selected_range_geometry_reacts_to_zoom(self):
        self.waveform.set_selected_range(1000, 2500)
        self.waveform.set_zoom(200)

        rect = self.waveform._selected_range_rect()

        self.assertEqual(self.waveform._ms_to_x(1000), 200)
        self.assertEqual(self.waveform._ms_to_x(2500), 500)
        self.assertEqual(rect.left(), 200)
        self.assertEqual(rect.width(), 300)

    def test_invalid_range_is_cleared_and_clear_removes_rect(self):
        self.waveform.set_selected_range(1000, 2500)
        self.waveform.set_selected_range(5000, 5000)
        self.assertIsNone(self.waveform._selected_range_ms)
        self.assertIsNone(self.waveform._selected_range_rect())

        self.waveform.set_selected_range(1000, 2500)
        self.waveform.clear_selected_range()
        self.assertIsNone(self.waveform._selected_range_ms)
        self.assertIsNone(self.waveform._selected_range_rect())

    def test_selected_range_is_clamped_to_duration(self):
        self.waveform.set_selected_range(-100, 12000)

        self.assertEqual(self.waveform._selected_range_ms, (0, 10000))

    def test_timeline_scrollbar_has_expanded_horizontal_hit_area(self):
        timeline = TimelineWidget()

        self.assertIn("QScrollBar::handle:horizontal", timeline.styleSheet())
        self.assertIn("height: 14px", timeline.styleSheet())
        self.assertIn("min-width: 72px", timeline.styleSheet())

    def test_selected_range_is_painted_when_it_overlaps_viewport(self):
        self.waveform.set_selected_range(1000, 2500)
        image = QImage(1000, 100, QImage.Format_ARGB32)
        image.fill(QColor("#000000"))

        self.waveform.render(image)

        cyan = QColor(Theme.CYAN)
        cyan_pixels = 0
        for x in range(image.width()):
            for y in range(image.height()):
                pixel = QColor(image.pixel(x, y))
                if pixel.red() == cyan.red() and pixel.green() == cyan.green() and pixel.blue() == cyan.blue():
                    cyan_pixels += 1
        self.assertGreater(cyan_pixels, 0)


class _FakeTrack:
    def __init__(self, segments):
        self.segments = segments
        self.selected_ids = set()
        self.selection_calls = []

    def set_selection(self, selected_ids):
        self.selected_ids = set(selected_ids)
        self.selection_calls.append(set(selected_ids))

    def update(self):
        pass


class _FakeWaveform:
    def __init__(self):
        self.selected_range = None
        self.clear_calls = 0

    def set_selected_range(self, start_ms, end_ms):
        self.selected_range = (start_ms, end_ms)

    def clear_selected_range(self):
        self.selected_range = None
        self.clear_calls += 1


class _FakeTimeline:
    def __init__(self, segments):
        self.container = SimpleNamespace(
            track=_FakeTrack(segments),
            waveform=_FakeWaveform(),
        )
        self.centered_times = []

    def center_on_time(self, time_ms):
        self.centered_times.append(time_ms)


@unittest.skipIf(TimelineController is None, "TimelineController dependencies are unavailable")
class TestTimelineControllerSelectionFrame(unittest.TestCase):
    def setUp(self):
        self.segment = SimpleNamespace(
            segment_id="seg-1",
            start_ms=1000,
            end_ms=2500,
        )
        self.ui = _FakeTimeline([self.segment])
        self.controller = TimelineController.__new__(TimelineController)
        self.controller.ui = self.ui

    def test_editor_selection_syncs_track_waveform_and_centers_midpoint(self):
        self.controller.sync_selection(0, "seg-1", SelectionSource.EDITOR)

        self.assertEqual(self.ui.container.track.selected_ids, {"seg-1"})
        self.assertEqual(self.ui.container.waveform.selected_range, (1000, 2500))
        self.assertEqual(self.ui.centered_times, [1750])

    def test_playback_selection_updates_waveform_without_editor_centering(self):
        self.controller.sync_selection(0, "seg-1", SelectionSource.PLAYBACK)

        self.assertEqual(self.ui.container.waveform.selected_range, (1000, 2500))
        self.assertEqual(self.ui.centered_times, [])

    def test_invalid_selection_clears_track_and_waveform(self):
        self.controller.sync_selection(0, "seg-1", SelectionSource.EDITOR)
        self.controller.sync_selection(-1, None, SelectionSource.PROGRAMMATIC)

        self.assertEqual(self.ui.container.track.selected_ids, set())
        self.assertIsNone(self.ui.container.waveform.selected_range)
        self.assertEqual(self.ui.container.waveform.clear_calls, 1)


@unittest.skipIf(
    TimelineWidget is None or SubtitleEditorWidget is None,
    "Timeline UI dependencies are unavailable",
)
class TestTimelineProductionSelectionBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_segments_refresh_stale_timeline_before_selection(self):
        timeline = TimelineWidget()
        timeline.load_project_data(10000, [], np.zeros((1000, 2)))
        provider = TimelineDataProvider()
        controller = TimelineController.__new__(TimelineController)
        controller.ui = timeline
        controller.data_provider = provider
        editor = SubtitleEditorWidget()
        editor.live_edit_applied.connect(
            lambda *_: controller.sync_from_editor_segments(editor.all_segments)
        )

        editor.all_segments = [
            {
                "id": "seg-1",
                "start": 1000,
                "end": 2500,
                "start_ms": 1000,
                "end_ms": 2500,
                "text": "Hello",
            }
        ]

        editor.render_page()

        self.assertEqual(len(provider.get_all_segments()), 1)
        self.assertEqual(len(timeline.container.track.segments), 1)
        controller.sync_selection(0, "seg-1", SelectionSource.EDITOR)
        self.assertEqual(timeline.container.track.selected_ids, {"seg-1"})
        self.assertEqual(timeline.container.waveform._selected_range_ms, (1000, 2500))

    def test_stale_cached_timing_drives_real_selection_range_and_center(self):
        timeline = TimelineWidget()
        timeline.load_project_data(900000, [], np.zeros((1000, 2)))
        provider = TimelineDataProvider()
        controller = TimelineController.__new__(TimelineController)
        controller.ui = timeline
        controller.data_provider = provider
        controller.selection_controller = None

        editor_segments = [{
            "id": "seg-85",
            "start": "00:06:43,062",
            "end": "00:06:50,422",
            "start_ms": 0,
            "end_ms": 0,
            "text": "...",
        }]
        controller.sync_from_editor_segments(editor_segments)

        centered_times = []
        timeline.center_on_time = centered_times.append
        controller.sync_selection(0, "seg-85", SelectionSource.EDITOR)

        self.assertEqual(
            timeline.container.waveform._selected_range_ms,
            (403062, 410422),
        )
        self.assertEqual(centered_times, [406742])

    def test_repeated_editor_activation_centers_after_playback_selection(self):
        segment = SimpleNamespace(segment_id="seg-1", start_ms=1000, end_ms=2500)
        timeline = _FakeTimeline([segment])
        controller = TimelineController.__new__(TimelineController)
        controller.ui = timeline
        selection_controller = SubtitleSelectionController()
        selection_controller.selection_changed.connect(controller.sync_selection)
        selection_controller.editor_activation_requested.connect(
            controller.sync_editor_activation
        )

        selection_controller.select(0, "seg-1", SelectionSource.PLAYBACK)
        selection_controller.request_editor_activation(0, "seg-1")
        selection_controller.select(0, "seg-1", SelectionSource.EDITOR)

        self.assertEqual(timeline.centered_times, [1750])


if __name__ == "__main__":
    unittest.main()
