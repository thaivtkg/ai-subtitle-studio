import sys
import unittest

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from core.demo_capture.errors import CaptureRunError
from ui.demo_capture.frame_normalizer import FrameNormalizer


class TestDemoCaptureFrameNormalizerC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_tc210_pad_smaller_frames_without_stretch(self):
        frame1 = QImage(100, 50, QImage.Format.Format_ARGB32)
        frame2 = QImage(200, 100, QImage.Format.Format_ARGB32)
        result = FrameNormalizer().normalize([frame1, frame2], 1.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].width(), 200)
        self.assertEqual(result[0].height(), 100)
        self.assertEqual(result[1].width(), 200)

    def test_tc211_centering_uses_deterministic_floor_division(self):
        frame1 = QImage(51, 51, QImage.Format.Format_ARGB32)
        frame2 = QImage(100, 100, QImage.Format.Format_ARGB32)
        result = FrameNormalizer().normalize([frame1, frame2], 1.0)
        self.assertEqual(result[0].width(), 100)

    def test_tc212_output_scale_scales_final_canvas(self):
        frame = QImage(100, 50, QImage.Format.Format_ARGB32)
        result = FrameNormalizer().normalize([frame], 2.0)
        self.assertEqual(result[0].width(), 200)
        self.assertEqual(result[0].height(), 100)

    def test_tc213_empty_sequence_fails(self):
        with self.assertRaises(CaptureRunError):
            FrameNormalizer().normalize([], 1.0)


if __name__ == "__main__":
    unittest.main()
