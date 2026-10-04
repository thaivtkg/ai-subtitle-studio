import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication
from ui.Gui import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_viewports_acceptance(qapp):
    progress_dir = tempfile.TemporaryDirectory()
    progress_file = Path(progress_dir.name) / "tutorial_progress.json"
    with patch("ui.Gui.RuntimePaths.get_tutorial_progress_file", return_value=progress_file):
        win = MainWindow(project_service=MagicMock(), media_import_service=MagicMock())

    try:
        viewports = [(1280, 720), (1366, 768)]
        for width, height in viewports:
            win.resize(width, height)
            win.show()
            qapp.processEvents()

            # Verify window size accommodates viewport
            assert win.width() >= 1200
            assert win.height() >= 700

            # Verify sidebar does not dominate viewport (fixed compact 64px width)
            sidebar_w = win.sidebar_scroll.width()
            assert sidebar_w <= 240, f"Sidebar too wide: {sidebar_w}px"

            # Verify all core pages switch cleanly without exceptions
            expected_mapping = [(0, 0), (1, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6)]
            from PySide6.QtTest import QTest
            for nav_idx, expected_stack_idx in expected_mapping:
                win.switch_page(nav_idx)
                for _ in range(50):
                    qapp.processEvents()
                    if win.stack.current_index == expected_stack_idx:
                        break
                    QTest.qWait(10)
                assert win.stack.current_index == expected_stack_idx

            # Verify recovery center can be invoked without layout breakage
            from ui.dialogs.recovery_center_dialog import RecoveryCenterDialog
            rec_dlg = RecoveryCenterDialog(
                entries_provider=lambda: [],
                live_session_id_provider=lambda: "live",
                restore_callback=lambda *a, **k: True,
                delete_callback=lambda *a, **k: True,
            )
            rec_dlg.resize(800, 500)
            rec_dlg.show()
            qapp.processEvents()
            rec_dlg.close()
            qapp.processEvents()

    finally:
        win.close()
        win.deleteLater()
        qapp.processEvents()
        progress_dir.cleanup()
