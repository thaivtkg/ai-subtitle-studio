import base64
import sys
import unittest
from pathlib import Path

from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QApplication

from core.tutorial.models import MediaSpec
from ui.tutorial.demo_media_viewer import DemoMediaViewer


class TestC3DemoMediaViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

        cls.test_dir = Path("test_media_c3")
        cls.test_dir.mkdir(exist_ok=True)

        cls.static_img = cls.test_dir / "static.png"
        cls.static_img.touch()

        cls.gif_img = cls.test_dir / "animated.gif"
        cls.gif_img.write_bytes(
            base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
        )

    def setUp(self):
        self.viewers = []

    def tearDown(self):
        for viewer in self.viewers:
            viewer.close()
            viewer.deleteLater()
        self.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        if cls.static_img.exists():
            cls.static_img.unlink()
        if cls.gif_img.exists():
            cls.gif_img.unlink()
        if cls.test_dir.exists():
            cls.test_dir.rmdir()

    def test_tc184_viewer_renders_static_image(self):
        """TC184: Viewer load thành công QPixmap từ đường dẫn tĩnh hợp lệ."""
        spec = MediaSpec(type="image", path=str(self.static_img))
        viewer = DemoMediaViewer()
        self.viewers.append(viewer)

        viewer.set_media(spec)

        self.assertIsNotNone(viewer.current_pixmap())
        self.assertIsNone(viewer.current_movie(), "Ảnh tĩnh không được dùng QMovie")

    def test_tc185_viewer_renders_and_controls_gif(self):
        """TC185: Viewer load và quản lý QMovie cho GIF."""
        spec = MediaSpec(type="gif", path=str(self.gif_img))
        viewer = DemoMediaViewer()
        self.viewers.append(viewer)

        viewer.set_media(spec)

        movie = viewer.current_movie()
        self.assertIsInstance(movie, QMovie, "Ảnh GIF phải được quản lý bằng QMovie")

        viewer.show()
        self.assertTrue(viewer.is_playing())

        viewer.hide()
        self.assertFalse(viewer.is_playing(), "QMovie phải dừng khi Viewer bị ẩn để tiết kiệm CPU")

    def test_unsupported_media_type_fails_gracefully(self):
        """Chống video/mp4 theo đúng scope Milestone C3."""
        spec = MediaSpec(type="video", path="test.mp4")
        viewer = DemoMediaViewer()
        self.viewers.append(viewer)

        with self.assertRaises(ValueError):
            viewer.set_media(spec)


if __name__ == "__main__":
    unittest.main()
