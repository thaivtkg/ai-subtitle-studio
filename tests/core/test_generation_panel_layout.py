import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtWidgets import (
        QApplication,
        QScrollArea,
        QWidget,
        QVBoxLayout,
    )
except (ModuleNotFoundError, ImportError, OSError):
    QApplication = None
    QScrollArea = None
    QWidget = None
    QVBoxLayout = None
    Qt = None
    QPoint = None

if QApplication is not None:
    from ui.subtitle_generation_panel import SubtitleGenerationPanel
else:
    SubtitleGenerationPanel = None


class _CheckpointManager:
    def load_checkpoint(self):
        return None


class _GenerationService:
    def __init__(self):
        self.checkpoint_manager = _CheckpointManager()
        self.project_service = None
        self.is_running = False
        self.on_progress = None
        self.on_error = None
        self.on_finish = None


@unittest.skipIf(
    SubtitleGenerationPanel is None,
    "PySide6 or generation panel dependencies unavailable",
)
class TestGenerationPanelLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        return SubtitleGenerationPanel(_GenerationService())

    def test_settings_use_a_resizable_vertical_scroll_area(self):
        panel = self._panel()
        scroll_area = getattr(panel, "settings_scroll_area", None)
        content = getattr(panel, "settings_scroll_content", None)

        self.assertIsInstance(scroll_area, QScrollArea)
        self.assertTrue(scroll_area.widgetResizable())
        self.assertEqual(
            scroll_area.horizontalScrollBarPolicy(),
            Qt.ScrollBarAlwaysOff,
        )
        self.assertIs(content, scroll_area.widget())

    def test_settings_controls_live_inside_scroll_content(self):
        panel = self._panel()
        content = getattr(panel, "settings_scroll_content", None)
        self.assertIsNotNone(content)

        for name in (
            "cmb_mode",
            "model_group",
            "cmb_model",
            "cmb_compute",
            "cmb_language",
            "chk_vad",
            "chk_fix_overlap",
            "spin_overlap_gap",
            "chk_word_timestamps",
            "cmb_batch_mode",
            "spin_batch_val",
            "btn_context_edit",
        ):
            with self.subTest(control=name):
                self.assertTrue(content.isAncestorOf(getattr(panel, name)))

    def test_action_footer_contains_actions_outside_scroll_area(self):
        panel = self._panel()
        footer = getattr(panel, "action_footer", None)
        scroll_area = getattr(panel, "settings_scroll_area", None)
        self.assertIsNotNone(footer)
        self.assertIsNotNone(scroll_area)

        for name in (
            "lbl_status",
            "progress_bar",
            "btn_generate",
            "btn_resume",
            "btn_cancel",
        ):
            with self.subTest(control=name):
                control = getattr(panel, name)
                self.assertTrue(footer.isAncestorOf(control))

        for name in ("btn_generate", "btn_resume", "btn_cancel"):
            with self.subTest(control=name):
                self.assertFalse(scroll_area.isAncestorOf(getattr(panel, name)))

    def test_constrained_height_keeps_action_footer_visible_and_settings_scrollable(self):
        for width, height in ((350, 500), (350, 600), (390, 500), (390, 600)):
            with self.subTest(width=width, height=height):
                host = QWidget()
                host.resize(width, height)
                host_layout = QVBoxLayout(host)
                panel = self._panel()
                host_layout.addWidget(panel)

                host.show()
                self.app.processEvents()

                footer = getattr(panel, "action_footer", None)
                scroll_area = getattr(panel, "settings_scroll_area", None)
                self.assertIsNotNone(footer)
                self.assertIsNotNone(scroll_area)

                footer_top = footer.mapTo(panel, QPoint(0, 0)).y()
                footer_bottom = footer_top + footer.height()
                self.assertLessEqual(
                    footer_bottom,
                    panel.contentsRect().bottom() + 4,
                )
                self.assertTrue(panel.btn_generate.isVisible())
                self.assertGreater(scroll_area.verticalScrollBar().maximum(), 0)

                host.close()


if __name__ == "__main__":
    unittest.main()
