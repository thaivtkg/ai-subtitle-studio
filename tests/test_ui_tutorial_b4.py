import sys
import unittest

import shiboken6
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from core.tutorial.models import CalloutPlacement, CalloutSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.spotlight_layer import SpotlightLayerAdapter


class MockStepControls:
    def next(self):
        pass

    def back(self):
        pass

    def skip_step(self):
        pass

    def retry(self):
        pass

    def cancel(self):
        pass


class TestMilestoneB4SpotlightLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.registry = AnchorRegistry()
        self.spotlight = SpotlightLayerAdapter(self.registry)
        self.host = QWidget()
        self.host.resize(800, 600)
        self.target = QPushButton("Target", self.host)
        self.target.setGeometry(100, 100, 200, 50)
        self.host.show()
        self.registry.register("target_btn", self.target)
        self.app.processEvents()

    def tearDown(self):
        self.spotlight.detach_host()
        if shiboken6.isValid(self.host):
            self.host.deleteLater()
        self.app.processEvents()

    def test_tc163_physical_hole_and_dim_widgets_geometry(self):
        result = self.registry.resolve("target_btn")
        self.assertTrue(self.spotlight.show_target(result.handle, CalloutSpec("T", "B"), MockStepControls()))
        self.app.processEvents()
        self.assertEqual(self.spotlight._top_dim.geometry(), QRect(0, 0, 800, 100))
        self.assertEqual(self.spotlight._bottom_dim.geometry(), QRect(0, 150, 800, 450))
        self.assertEqual(self.spotlight._left_dim.geometry(), QRect(0, 100, 100, 50))
        self.assertEqual(self.spotlight._right_dim.geometry(), QRect(300, 100, 500, 50))

    def test_tc162_dim_widgets_are_mouse_blocking(self):
        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(result.handle, CalloutSpec("T", "B"), MockStepControls())
        self.assertFalse(self.spotlight._top_dim.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_tc164_callout_positions_correctly(self):
        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(result.handle, CalloutSpec("Title", "Body"), MockStepControls())
        self.app.processEvents()
        self.assertTrue(self.spotlight._callout_widget.isVisible())
        self.assertEqual(self.spotlight._callout_widget.title_label.text(), "Title")
        self.assertEqual(self.spotlight._callout_widget.y(), 160)

    def test_tc165_dim_widgets_update_on_resize_or_move(self):
        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(result.handle, CalloutSpec("T", "B"), MockStepControls())
        self.target.setGeometry(200, 200, 200, 50)
        self.app.processEvents()
        self.assertEqual(self.spotlight._top_dim.geometry(), QRect(0, 0, 800, 200))

    def test_callout_placement_and_cancel_control(self):
        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(
            result.handle,
            CalloutSpec("Title", "Body", placement=CalloutPlacement.TOP),
            MockStepControls(),
        )
        self.assertLess(self.spotlight._callout_widget.y(), 100)
        self.assertEqual(self.spotlight._callout_widget.buttons["cancel"].text(), "End Tour")
