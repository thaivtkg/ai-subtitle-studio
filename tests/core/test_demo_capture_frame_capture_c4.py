import sys
import unittest

from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from core.demo_capture.models import CaptureScope, CaptureTarget
from ui.demo_capture.frame_capture import FrameCaptureService


class MockResolver:
    def __init__(self, widget):
        self.widget = widget

    def resolve_widget(self, semantic_id: str):
        return self.widget


class TestDemoCaptureFrameCaptureC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.root = QWidget()
        self.root.resize(800, 600)
        self.btn = QPushButton(parent=self.root)
        self.btn.resize(100, 50)
        self.service = FrameCaptureService(MockResolver(self.btn))

    def tearDown(self):
        self.root.deleteLater()
        self.app.processEvents()

    def test_tc206_target_region_applies_correct_padding(self):
        self.btn.move(100, 100)
        image = self.service.capture(CaptureTarget("btn", padding=16), self.root)
        self.assertEqual(image.width(), 132)
        self.assertEqual(image.height(), 82)

    def test_tc207_target_region_clips_out_of_bounds(self):
        self.btn.move(0, 0)
        image = self.service.capture(CaptureTarget("btn", padding=16), self.root)
        self.assertEqual(image.width(), 116)
        self.assertEqual(image.height(), 66)

    def test_tc208_full_window_grabs_main_window(self):
        target = CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None, padding=999)
        image = self.service.capture(target, self.root)
        self.assertEqual(image.width(), 800)
        self.assertEqual(image.height(), 600)

    def test_tc209_dynamic_geometry_without_caching(self):
        self.btn.move(100, 100)
        target = CaptureTarget("btn", padding=0)
        image1 = self.service.capture(target, self.root)
        self.assertEqual(image1.width(), 100)
        self.btn.resize(200, 50)
        self.btn.move(200, 200)
        image2 = self.service.capture(target, self.root)
        self.assertEqual(image2.width(), 200)


if __name__ == "__main__":
    unittest.main()
