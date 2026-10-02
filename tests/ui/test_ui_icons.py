import sys
import unittest

from PySide6.QtWidgets import QApplication

from ui.queue_item import QueueItemWidget


class TestQueueDeleteIcon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_queue_delete_button_has_visible_icon(self):
        item = QueueItemWidget(r"C:\\temp\\sample.mp4", "Ready", False, "00:01:00")
        button = item.btn_remove

        self.assertFalse(button.icon().isNull())
        self.assertGreater(button.iconSize().width(), 0)
        self.assertGreater(button.iconSize().height(), 0)


if __name__ == "__main__":
    unittest.main()
