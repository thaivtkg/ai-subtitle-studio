import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestUiPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_custom_coordinate_spinboxes_use_dark_theme_styles(self):
        from ui.subtitle_inspector_panel import SubtitleInspectorPanel
        from ui.theme import Theme

        panel = SubtitleInspectorPanel()
        stylesheet = panel.styleSheet()
        self.assertIn("QDoubleSpinBox", stylesheet)
        self.assertIn(Theme.BG_APP, stylesheet)
        self.assertIn(Theme.TEXT_PRIMARY, stylesheet)
        self.assertIn(Theme.BORDER, stylesheet)
        self.assertIn("QDoubleSpinBox:hover", stylesheet)
        self.assertIn("QDoubleSpinBox:focus", stylesheet)
        self.assertIn("QDoubleSpinBox:disabled", stylesheet)
        self.assertIn("QDoubleSpinBox::up-button", stylesheet)
        self.assertIn("QDoubleSpinBox::down-button", stylesheet)
        panel.deleteLater()

    def test_manual_hardsub_success_schedules_prompt_cleanup(self):
        from ui.Gui import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._register_artifact = MagicMock()
        window.project_service = SimpleNamespace(current_project=None)
        window.progress_bar = MagicMock()
        window.page_dashboard = SimpleNamespace(quick_progress=MagicMock())
        window.start_btn = MagicMock()
        window.cancel_btn = MagicMock()
        window.progress_anim = MagicMock()
        window.lbl_speed_eta = MagicMock()
        window.page_dashboard.card_status_val = MagicMock()

        with patch("ui.Gui.Toast.show_success"), patch(
            "ui.Gui.QTimer.singleShot"
        ) as single_shot:
            window._on_manual_hardsub_success("done", "output.mp4")

        self.assertEqual(single_shot.call_count, 1)
        delay, cleanup = single_shot.call_args.args
        self.assertGreaterEqual(delay, 300)
        self.assertLessEqual(delay, 500)
        self.assertEqual(cleanup.__name__, "_cleanup_ui_after_task")

        window._cleanup_ui_after_task()
        window.progress_bar.setValue.assert_called_with(0)
        window.page_dashboard.quick_progress.setValue.assert_called_with(0)
        window.start_btn.setEnabled.assert_called_with(True)
        window.cancel_btn.setEnabled.assert_called_with(False)
        window.page_dashboard.card_status_val.setText.assert_called_with("Idle")


if __name__ == "__main__":
    unittest.main()
