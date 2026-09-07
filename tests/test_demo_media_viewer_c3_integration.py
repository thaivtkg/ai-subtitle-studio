import base64
import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from core.tutorial.environment import TourEnvironment
from core.tutorial.models import (
    CalloutSpec,
    DemoSpec,
    SafetySpec,
    TourDefinition,
    TourStep,
    TourStepType,
)
from core.tutorial.tour_engine import TourEngine
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.demo_media_viewer import DemoMediaViewer
from ui.tutorial.dialog_observer import DialogLifecycleObserver
from ui.tutorial.interaction_observer import InteractionObserverAdapter
from ui.tutorial.navigation_adapter import AppRouter, NavigationAdapter
from ui.tutorial.spotlight_layer import SpotlightLayerAdapter


class MockAppRouter(AppRouter):
    def current_index(self):
        return 0

    def current_subroute(self):
        return None

    def navigate_to_index(self, index, subroute=None):
        return "mock_op"


class FakeCatalog:
    def __init__(self, guide):
        self._guide = guide

    def get_guide(self, guide_id):
        return self._guide if self._guide.guide_id == guide_id else None


class TestC3TourIntegrationRED(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.test_dir = Path("test_media_integration")
        cls.test_dir.mkdir(exist_ok=True)
        cls.static_img = cls.test_dir / "static.png"
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
        self.host_widget = QWidget()
        self.host_widget.resize(800, 600)
        self.host_widget.show()

        self.anchor_registry = AnchorRegistry()
        self.spotlight = SpotlightLayerAdapter(self.anchor_registry, self.host_widget)
        self.spotlight.attach_host(self.host_widget)
        self.dialog_observer = DialogLifecycleObserver(self.host_widget)
        self.engine = TourEngine(
            catalog=None,
            anchor_registry=self.anchor_registry,
            navigation=NavigationAdapter(MockAppRouter(), self.host_widget),
            interaction_observer=InteractionObserverAdapter(
                self.anchor_registry, parent=self.host_widget
            ),
            spotlight=self.spotlight,
            dialog_observer=self.dialog_observer,
            progress_store=None,
            environment=TourEnvironment(lambda _: True),
            parent=self.host_widget,
        )
        self.app.processEvents()

    def tearDown(self):
        self.engine.cancel("TEST_CLEANUP")
        self.spotlight.detach_host()
        self.host_widget.deleteLater()
        self.app.processEvents()

    def _find_media_viewer(self):
        return self.host_widget.findChild(DemoMediaViewer, "demo_media_viewer")

    def _demo_spec(self):
        return DemoSpec(
            asset=str(self.static_img),
            media_type="image",
            fit="contain",
        )

    def test_tc184_tour_engine_dispatches_demo_spec_to_spotlight(self):
        """TC184: Domain DemoSpec được map vào DemoMediaViewer ở Presentation."""
        step = TourStep(
            step_id="demo_step",
            step_type=TourStepType.DEMO,
            callout=CalloutSpec(title="Demo Title", body="Demo Body"),
            safety=SafetySpec(allow_back=True),
            demo=self._demo_spec(),
        )
        guide = TourDefinition(
            schema_version=1,
            guide_id="demo_guide",
            content_version=1,
            title="Demo",
            category="cat",
            estimated_minutes=1,
            steps=(step,),
        )
        self.engine._catalog = FakeCatalog(guide)

        self.assertTrue(self.engine.start("demo_guide"))
        self.app.processEvents()

        viewer = self._find_media_viewer()
        self.assertIsNotNone(
            viewer,
            "Spotlight không compose DemoMediaViewer khi nhận DemoSpec.",
        )
        self.assertTrue(viewer.isVisible(), "DemoMediaViewer phải hiển thị.")
        self.assertIsNotNone(
            viewer.current_pixmap(),
            "DemoSpec chưa được resolve thành MediaSpec và nạp vào Viewer.",
        )
        self.assertFalse(viewer.current_pixmap().isNull())

    def test_tc185_lifecycle_cleanup_on_next(self):
        """TC185: Rời DEMO step phải ẩn hoặc hủy DemoMediaViewer."""
        steps = (
            TourStep(
                step_id="step_demo",
                step_type=TourStepType.DEMO,
                callout=CalloutSpec("T1", "B1"),
                safety=SafetySpec(allow_back=True),
                demo=self._demo_spec(),
            ),
            TourStep(
                step_id="step_info",
                step_type=TourStepType.INFO,
                callout=CalloutSpec("T2", "B2"),
                safety=SafetySpec(allow_back=True),
            ),
        )
        guide = TourDefinition(
            schema_version=1,
            guide_id="lifecycle_guide",
            content_version=1,
            title="Lifecycle",
            category="cat",
            estimated_minutes=1,
            steps=steps,
        )
        self.engine._catalog = FakeCatalog(guide)

        self.assertTrue(self.engine.start("lifecycle_guide"))
        self.app.processEvents()
        viewer = self._find_media_viewer()
        self.assertIsNotNone(viewer, "Spotlight thiếu DemoMediaViewer ở step 1")
        self.assertTrue(viewer.isVisible())

        self.engine.next()
        self.app.processEvents()

        new_viewer = self._find_media_viewer()
        if new_viewer is not None:
            self.assertFalse(
                new_viewer.isVisible(),
                "Viewer không bị ẩn khi sang step không có DEMO.",
            )


if __name__ == "__main__":
    unittest.main()
