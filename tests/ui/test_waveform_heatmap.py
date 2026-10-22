import pytest
import numpy as np
from PySide6.QtGui import QColor
from ui.timeline.waveform_view import WaveformView


def test_tc_heatmap_01_color_by_energy():
    """TC-HEATMAP-01: Xác định màu sắc sóng âm theo biên độ RMS / năng lượng"""
    view = WaveformView()
    assert hasattr(view, "get_heatmap_color")

    # Đỉnh cao la hét / combat (> 0.75 amplitude hoặc > -14 dB) -> Cam Đỏ
    loud_color = view.get_heatmap_color(min_peak=-0.85, max_peak=0.85)
    assert loud_color.name() == QColor(239, 68, 68).name()

    # Đáy thấp thì thầm (< 0.15 amplitude hoặc < -26 dB) -> Xanh Ngọc
    whisper_color = view.get_heatmap_color(min_peak=-0.08, max_peak=0.08)
    assert whisper_color.name() == QColor(6, 182, 212).name()

    # Mức hội thoại thông thường -> Xanh Lục chuẩn
    normal_color = view.get_heatmap_color(min_peak=-0.4, max_peak=0.4)
    assert normal_color.name() == QColor(16, 185, 129).name()


def test_heatmap_toggle_disabled():
    """Khi heatmap_enabled=False, trả về màu mặc định của theme"""
    view = WaveformView()
    view.heatmap_enabled = False
    color = view.get_heatmap_color(min_peak=-0.9, max_peak=0.9)
    # Default waveform color
    assert color != QColor(239, 68, 68)
