import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QRect
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

from ui.timeline.timeline_widget import TimelineWidget


def test_tc_max_01_and_02_toggle_maximize_restore(qapp):
    """AC-MAX-01 & AC-MAX-02: Phóng to và thu nhỏ cửa sổ có phục hồi chính xác geometry"""
    from ui.Gui import MainWindow

    win = MainWindow()
    win.show()
    qapp.processEvents()

    # 1. Phóng to
    win.showMaximized()
    qapp.processEvents()
    assert win.isMaximized() is True

    # 2. Bấm nút thu nhỏ về bình thường
    win._toggle_maximize()
    qapp.processEvents()
    assert win.isMaximized() is False
    assert win.width() == 1366
    assert win.height() == 768
    assert win.btn_maximize.text() == "🗖"

    # 3. Bấm tiếp phóng to
    win._toggle_maximize()
    qapp.processEvents()
    assert win.isMaximized() is True
    assert win.btn_maximize.text() == "🗗"
    win.close()


def test_tc_max_03_topbar_double_click_toggles_maximize(qapp):
    """AC-MAX-03: Nhấp đúp chuột vào thanh Topbar (Y <= 42) kích hoạt phóng to / thu nhỏ"""
    from ui.Gui import MainWindow

    win = MainWindow()
    win.show()
    qapp.processEvents()

    initial_max = win.isMaximized()

    # Double click at topbar (y=20 <= 42)
    ev_dbl = QMouseEvent(
        QMouseEvent.MouseButtonDblClick,
        QPointF(200, 20),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    win.mouseDoubleClickEvent(ev_dbl)
    qapp.processEvents()

    assert win.isMaximized() != initial_max
    win.close()


def test_tc_zoom_01_and_02_timeline_zoom_and_wheel(qapp):
    """AC-ZOOM: Timeline zoom và Ctrl+Wheel zoom thay đổi tỷ lệ hiển thị waveform"""
    tl = TimelineWidget()
    assert tl.pixels_per_second == 100

    # Phóng to
    tl.set_zoom(140)
    assert tl.pixels_per_second == 140
    assert tl.container.waveform.pixels_per_second == 140
    assert tl.container.track.pixels_per_second == 140

    # Thu nhỏ bằng Ctrl + Wheel
    # delta > 0: zoom in, delta < 0: zoom out
    wheel_ev = QWheelEvent(
        QPointF(100, 50),
        QPointF(100, 50),
        QPoint(0, 0),
        QPoint(0, -120),  # cuộn xuống
        Qt.NoButton,
        Qt.ControlModifier,
        Qt.ScrollUpdate,
        False,
    )
    tl.wheelEvent(wheel_ev)
    assert tl.pixels_per_second == 120
