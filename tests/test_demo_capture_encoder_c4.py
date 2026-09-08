import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QImage

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from ui.demo_capture.encoder import PillowAssetEncoder


def image(width, height, color):
    frame = QImage(width, height, QImage.Format.Format_RGBA8888)
    frame.fill(QColor(*color))
    return frame


class TestPillowAssetEncoderC4(unittest.TestCase):
    def test_tc217_png_is_decodable_and_preserves_pixels(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.png"
            PillowAssetEncoder().encode_png(image(3, 2, (10, 20, 30, 255)), path)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            with Image.open(path) as decoded:
                self.assertEqual(decoded.size, (3, 2))
                self.assertEqual(decoded.convert("RGBA").getpixel((1, 1)), (10, 20, 30, 255))

    def test_tc218_gif_preserves_frames_delay_and_loop_without_coalescing(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.gif"
            PillowAssetEncoder().encode_gif(
                [
                    image(2, 2, (255, 0, 0, 255)),
                    image(2, 2, (0, 0, 255, 255)),
                    image(2, 2, (0, 0, 255, 255)),
                ],
                path,
                fps=10,
            )
            with Image.open(path) as decoded:
                self.assertEqual(decoded.n_frames, 3)
                self.assertEqual(decoded.info["duration"], 100)
                self.assertEqual(decoded.info["loop"], 0)
                for index in range(decoded.n_frames):
                    decoded.seek(index)
                    self.assertEqual(decoded.info["duration"], 100)

    def test_tc219_gif_requires_two_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CaptureRunError) as error:
                PillowAssetEncoder().encode_gif(
                    [image(2, 2, (0, 0, 0, 255))],
                    Path(directory) / "one.gif",
                    fps=10,
                )
            self.assertEqual(error.exception.error_code, CaptureErrorCode.ENCODE_FAILED)


if __name__ == "__main__":
    unittest.main()
