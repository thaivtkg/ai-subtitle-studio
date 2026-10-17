from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from ui.Gui import MainWindow
from tests.uat.conftest import MockProjectService


def _is_inside(widget, ancestor):
    while widget is not None:
        if widget is ancestor:
            return True
        widget = widget.parentWidget()
    return False


def test_drawer_stays_above_timeline_dock_in_workspace(qapp, tmp_path):
    window = MainWindow(project_service=MockProjectService(str(tmp_path)))
    window.resize(1200, 800)
    window.show()
    QTest.qWait(100)

    window.switch_page(1)  # Video Workspace -> timeline dock visible
    QTest.qWait(100)
    assert window.timeline_dock.isVisible()

    window._toggle_ai_drawer()
    QTest.qWait(500)

    drawer = window.generation_drawer
    # Probe the bottom of the drawer, where the timeline dock lives.
    probe = drawer.mapToGlobal(QPoint(drawer.width() // 2, drawer.height() - 20))
    hit = QApplication.widgetAt(probe)
    assert _is_inside(hit, drawer), f"drawer covered by {hit!r}"
    assert not _is_inside(hit, window.timeline_dock)

    # Leaving and re-entering the workspace must not bury the drawer either.
    window.switch_page(0)
    window.switch_page(1)
    QTest.qWait(100)
    hit = QApplication.widgetAt(probe)
    assert _is_inside(hit, drawer), f"drawer covered by {hit!r}"

    # Panel must resolve editor segments from MainWindow (no ImportError).
    assert window.generation_panel._get_current_segments() is window.sub_editor.all_segments

    # Shared reload helper (external SRT / source switch) must reach MainWindow.
    from tests.uat.conftest import generate_fake_segments
    window.sub_editor.save_draft = lambda *a, **k: None  # no disk I/O in test
    assert window.generation_panel._replace_editor_segments(generate_fake_segments(3))
    assert len(window.sub_editor.all_segments) == 3
    assert len(window.timeline_data_provider.get_all_segments()) == 3
    window.close()
