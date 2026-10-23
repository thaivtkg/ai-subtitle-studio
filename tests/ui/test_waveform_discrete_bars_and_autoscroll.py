# -*- coding: utf-8 -*-
import pytest
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget
from ui.timeline.waveform_view import WaveformView
from ui.timeline.timeline_widget import TimelineWidget
from core.timeline.timeline_integration import TimelineVideoSync
from core.timeline.timeline_state import TimelineStateManager


def test_waveform_auto_gain_calculation():
    view = WaveformView()

    # 1. Low volume audio (peak amplitude ~ 0.05) -> auto gain should scale up
    quiet_peaks = np.full((100, 2), 0.05)
    quiet_peaks[:, 0] = -0.05
    gain_quiet = view._calculate_visual_gain(quiet_peaks)
    assert gain_quiet > 1.5
    assert gain_quiet <= 4.0

    # 2. High volume audio (peak amplitude ~ 0.85) -> auto gain should stay 1.0
    loud_peaks = np.full((100, 2), 0.85)
    loud_peaks[:, 0] = -0.85
    gain_loud = view._calculate_visual_gain(loud_peaks)
    assert gain_loud == 1.0

    # 3. set_data applies the visual gain
    view.set_data(quiet_peaks, duration_ms=1000)
    assert view.visual_gain == gain_quiet
    view.close()


def test_waveform_render_discrete_bars_no_crash(qapp):
    view = WaveformView()
    peaks = np.array([[-0.1, 0.1], [-0.5, 0.5], [-0.02, 0.02], [-0.8, 0.8]])
    view.set_data(peaks, duration_ms=40)
    view.resize(300, 75)
    # Trigger paintEvent
    view.repaint()
    view.close()


class MockPlayer(QObject):
    timeline_position_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.player = MockMediaPlayer()

    def cancel_segment_playback(self, pause=True):
        pass

    def play_segment(self, start, end):
        pass


class MockMediaPlayer(QObject):
    playingChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self._pos = 0

    def position(self):
        return self._pos


def test_autoscroll_resets_on_playing_changed(qapp):
    timeline = TimelineWidget()
    timeline.load_project_data(duration_ms=60000, segments=[])
    timeline.resize(400, 150)

    player = MockPlayer()
    state_mgr = TimelineStateManager()
    sync = TimelineVideoSync(player, timeline, state_mgr)

    # User scrolls -> disables auto-scroll
    timeline.auto_scroll_enabled = False
    assert timeline.auto_scroll_enabled is False

    # Video starts playing -> automatically resets auto-scroll
    player.player.playingChanged.emit(True)
    assert timeline.auto_scroll_enabled is True

    timeline.close()


def test_playhead_edge_guard_auto_scroll(qapp):
    timeline = TimelineWidget()
    timeline.load_project_data(duration_ms=120000, segments=[])
    timeline.resize(400, 150)
    timeline.show()

    # User scrolls away to examine earlier segment
    timeline.auto_scroll_enabled = False

    # Playhead moves far to the right (beyond 75% of viewport width)
    # At 100px/s, 10s = 1000px, which exceeds 75% of 400px viewport (300px)
    timeline.update_playhead(10000)

    # Edge-Guard should have automatically re-enabled auto_scroll_enabled
    assert timeline.auto_scroll_enabled is True
    # Scrollbar should have scrolled forward towards the playhead
    assert timeline.horizontalScrollBar().value() > 0

    timeline.close()
