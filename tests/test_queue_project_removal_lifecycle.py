import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.queue_manager import QueueManager
from ui.Gui import MainWindow


class QueueProjectRemovalLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        queue = QueueManager()
        project_service = SimpleNamespace(
            current_project=SimpleNamespace(name="Project A", project_id="A"),
            project_dir=r"D:\Temp\A.ai-subtitle",
        )

        def close_project():
            project_service.current_project = None
            project_service.project_dir = None

        project_service.close_project = MagicMock(side_effect=close_project)
        window = SimpleNamespace(
            queue_mgr=queue,
            _queue_project_dirs={},
            project_service=project_service,
            revision_tracker=MagicMock(),
            autosave_coordinator=MagicMock(),
            canonical_save_coordinator=SimpleNamespace(
                enabled=True,
                flush_now=MagicMock(return_value=True),
                cancel_pending=MagicMock(),
            ),
            recovery_manager=MagicMock(),
            video_player=SimpleNamespace(
                cleanup=MagicMock(),
                sub_controller=SimpleNamespace(load_srt=MagicMock()),
            ),
            timeline_widget=SimpleNamespace(clear=MagicMock()),
            sub_editor=SimpleNamespace(
                all_segments=[],
                render_page=MagicMock(),
                commit_pending_edit=MagicMock(),
            ),
            quality_inspector_panel=SimpleNamespace(set_segments=MagicMock()),
            on_queue_item_clicked=MagicMock(),
            _update_canonical_save_status=MagicMock(),
        )
        queue.item_removed.connect(
            lambda item_key: MainWindow.on_queue_item_removed_handler(window, item_key)
        )
        return window

    def add_item(self, window, key, project_id):
        window.queue_mgr._items[key] = {
            "video_path": f"D:\\Temp\\{key}.mp4",
            "srt_path": None,
            "status": "Waiting",
            "metadata": None,
            "project_id": project_id,
            "project_root": f"D:\\Temp\\{key}.ai-subtitle",
        }

    def test_QR01_remove_last_active_item_closes_project(self):
        window = self.make_window()
        self.add_item(window, "A", "A")
        window.queue_mgr.active_item_key = "A"
        window.queue_mgr.active_vid = r"D:\Temp\A.mp4"

        self.assertTrue(MainWindow._on_queue_remove_requested(window, "A"))

        self.assertEqual(window.queue_mgr.get_items(), {})
        self.assertIsNone(window.project_service.current_project)
        self.assertIsNone(window.project_service.project_dir)
        window.revision_tracker.reset_for_new_document.assert_called_once_with()
        window._update_canonical_save_status.assert_called()

    def test_QR02_active_remove_selects_remaining_project(self):
        window = self.make_window()
        self.add_item(window, "A", "A")
        self.add_item(window, "B", "B")
        window.queue_mgr.active_item_key = "A"
        window.queue_mgr.active_vid = r"D:\Temp\A.mp4"

        def activate(item_key):
            item = window.queue_mgr.get_item(item_key)
            window.project_service.current_project = SimpleNamespace(
                name="Project B", project_id=item["project_id"]
            )
            window.project_service.project_dir = item["project_root"]

        window.on_queue_item_clicked.side_effect = activate

        self.assertTrue(MainWindow._on_queue_remove_requested(window, "A"))

        self.assertEqual(window.queue_mgr.active_item_key, "B")
        self.assertEqual(window.project_service.current_project.project_id, "B")
        window.on_queue_item_clicked.assert_called_once_with("B")

    def test_QR03_non_active_remove_keeps_active_project(self):
        window = self.make_window()
        self.add_item(window, "A", "A")
        self.add_item(window, "B", "B")
        window.queue_mgr.active_item_key = "A"
        window.queue_mgr.active_vid = r"D:\Temp\A.mp4"

        self.assertTrue(MainWindow._on_queue_remove_requested(window, "B"))

        self.assertEqual(window.queue_mgr.active_item_key, "A")
        self.assertEqual(window.project_service.current_project.project_id, "A")
        window.on_queue_item_clicked.assert_not_called()
        window.canonical_save_coordinator.flush_now.assert_not_called()

    def test_QR04_flush_failure_aborts_active_remove(self):
        window = self.make_window()
        self.add_item(window, "A", "A")
        window.queue_mgr.active_item_key = "A"
        window.queue_mgr.active_vid = r"D:\Temp\A.mp4"
        window.canonical_save_coordinator.flush_now.return_value = False

        self.assertFalse(MainWindow._on_queue_remove_requested(window, "A"))

        self.assertIn("A", window.queue_mgr.get_items())
        self.assertEqual(window.queue_mgr.active_item_key, "A")
        self.assertEqual(window.project_service.current_project.project_id, "A")
        window.sub_editor.commit_pending_edit.assert_called_once_with()
        window.on_queue_item_clicked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
