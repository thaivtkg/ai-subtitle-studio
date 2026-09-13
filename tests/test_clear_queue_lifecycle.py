import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.Gui import MainWindow
    from ui.SubEditor import SubtitleEditorWidget
except (ImportError, ModuleNotFoundError):
    QApplication = None
    MainWindow = None
    SubtitleEditorWidget = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestClearQueueLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_clear_queue_closes_project_and_resets_revision_state(self):
        project_service = MagicMock()
        revision_tracker = MagicMock()
        queue_mgr = MagicMock()
        queue_mgr.get_items.return_value = {}
        fake_window = SimpleNamespace(
            queue_mgr=queue_mgr,
            queue_ui=MagicMock(),
            page_dashboard=SimpleNamespace(lbl_queue_overview=MagicMock()),
            out_input=MagicMock(text=MagicMock(return_value="")),
            video_player=SimpleNamespace(
                cleanup=MagicMock(),
                sub_controller=SimpleNamespace(load_srt=MagicMock()),
            ),
            timeline_widget=SimpleNamespace(clear=MagicMock()),
            sub_editor=SimpleNamespace(
                all_segments=[{"text": "unsaved"}],
                render_page=MagicMock(),
            ),
            project_service=project_service,
            revision_tracker=revision_tracker,
        )

        MainWindow.on_queue_updated(fake_window)

        project_service.close_project.assert_called_once_with()
        revision_tracker.reset_for_new_document.assert_called_once_with()

    def test_empty_editor_page_clears_current_subtitle_context(self):
        editor = SubtitleEditorWidget()
        editor.all_segments = [
            {
                "stt": "84",
                "start": "00:06:40,812",
                "end": "00:06:43,062",
                "text": "sample",
            }
        ]
        editor.render_page()
        editor.select_segment(0)

        editor.all_segments.clear()
        editor.render_page()

        self.assertEqual(editor.current_index, -1)
        self.assertEqual(editor.editor_group.lbl_title.text(), "Current Subtitle: None")


if __name__ == "__main__":
    unittest.main()
