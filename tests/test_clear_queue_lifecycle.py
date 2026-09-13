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

    def test_empty_queue_clears_media_views_without_closing_project_context(self):
        project_service = MagicMock()
        revision_tracker = MagicMock()
        recovery_manager = MagicMock()
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
            recovery_manager=recovery_manager,
        )

        MainWindow.on_queue_updated(fake_window)

        fake_window.video_player.cleanup.assert_called_once_with()
        fake_window.timeline_widget.clear.assert_called_once_with()
        self.assertEqual(fake_window.sub_editor.all_segments, [])
        fake_window.sub_editor.render_page.assert_called_once_with()
        fake_window.video_player.sub_controller.load_srt.assert_called_once_with(None)
        project_service.close_project.assert_not_called()
        revision_tracker.reset_for_new_document.assert_not_called()
        recovery_manager.finalize_clean_shutdown.assert_not_called()

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
