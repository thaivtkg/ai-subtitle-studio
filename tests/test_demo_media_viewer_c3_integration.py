import base64
import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from core.tutorial.models import (
    CalloutSpec,
    MediaSpec,
    SafetySpec,
    TourStep,
    TourStepType,
)
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.demo_media_viewer import DemoMediaViewer
from ui.tutorial.spotlight_layer import SpotlightLayerAdapter


class TestC3DemoMediaViewerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.test_dir = Path("test_media_c3_integration")
        cls.test_dir.mkdir(exist_ok=True)
        cls.static_img = cls.test_dir / "demo.png"
        cls.static_img.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
                "+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
        )

    @classmethod
    def tearDownClass(cls):
        if cls.static_img.exists():
            cls.static_img.unlink()
        if cls.test_dir.exists():
            cls.test_dir.rmdir()

    def setUp(self):
        self.host = QWidget()
        self.host.resize(640, 480)
        self.host.show()
        self.spotlight = SpotlightLayerAdapter(AnchorRegistry(), self.host)
        self.app.processEvents()

    def tearDown(self):
        self.spotlight.detach_host()
        self.host.deleteLater()
        self.app.processEvents()

    def test_demo_step_accepts_media_spec(self):
        """C3.4: TourStep phải mang được media contract của DEMO step."""
        media = MediaSpec(type="image", path=str(self.static_img))

        step = TourStep(
            step_id="demo-media",
            step_type=TourStepType.DEMO,
            callout=CalloutSpec("Demo", "Body"),
            safety=SafetySpec(allow_back=True),
            media=media,
        )

        self.assertIs(step.media, media)

    def test_spotlight_composes_demo_media_viewer_into_host(self):
        """C3.4: show_demo phải compose DemoMediaViewer vào UI tree."""
        media = MediaSpec(type="image", path=str(self.static_img))

        self.spotlight.show_demo(media, CalloutSpec("Demo", "Body"), None)
        self.app.processEvents()

        viewer = self.host.findChild(DemoMediaViewer, "demo_media_viewer")
        self.assertIsNotNone(viewer)
        self.assertIs(viewer.parentWidget(), self.host)
        self.assertIsNotNone(viewer.current_pixmap())


if __name__ == "__main__":
    unittest.main()
