import sys
import unittest

import shiboken6
from PySide6.QtCore import QPointF, QRect, QEvent, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

from core.tutorial.models import CalloutPlacement, CalloutSpec, SafetySpec, TourState
from core.tutorial.tour_engine import TourControlsFacade
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


class StubEngine:
    def __init__(self):
        self._current_step_index = 1
        self._state = TourState.WAITING_ACTION
        self._step = type("Step", (), {"safety": SafetySpec(allow_back=True, allow_skip_step=False)})()

    def state(self):
        return self._state

    def current_step(self):
        return self._step

    def next(self):
        pass

    def back(self):
        pass

    def skip_step(self):
        pass

    def cancel(self, reason):
        pass

    def retry(self):
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

    def test_tc162_host_switch_hides_old_mask_immediately(self):
        first = self.registry.resolve("target_btn")
        self.spotlight.show_target(first.handle, CalloutSpec("T1", "B1"), MockStepControls())
        self.app.processEvents()
        old_top = self.spotlight._top_dim

        dialog = QDialog(self.host)
        dialog.resize(400, 300)
        dialog_target = QPushButton("Dialog target", dialog)
        dialog_target.setGeometry(50, 50, 100, 30)
        dialog.show()
        self.registry.register("dialog_target", dialog_target)
        second = self.registry.resolve("dialog_target")
        self.spotlight.show_target(second.handle, CalloutSpec("T2", "B2"), MockStepControls())

        self.assertFalse(old_top.isVisible())
        self.assertIs(self.spotlight._top_dim.parent(), dialog)
        dialog.deleteLater()

    def test_tc163_and_tc164_real_hit_testing(self):
        outside = QPushButton("Outside", self.host)
        outside.setGeometry(400, 400, 100, 50)
        outside.show()
        target_clicks = []
        outside_clicks = []
        self.target.clicked.connect(lambda: target_clicks.append(True))
        outside.clicked.connect(lambda: outside_clicks.append(True))

        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(result.handle, CalloutSpec("T", "B"), MockStepControls())
        self.app.processEvents()

        target_point = self.target.mapTo(self.host, self.target.rect().center())
        outside_point = outside.mapTo(self.host, outside.rect().center())
        target_hit = self.host.childAt(target_point)
        outside_hit = self.host.childAt(outside_point)
        self.assertIs(target_hit, self.target)
        self.assertIsInstance(outside_hit, DimWidget)

        for hit in (target_hit, outside_hit):
            self.app.sendEvent(
                hit,
                QMouseEvent(
                    QEvent.Type.MouseButtonPress,
                    QPointF(2, 2), QPointF(2, 2),
                    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                ),
            )
            self.app.sendEvent(
                hit,
                QMouseEvent(
                    QEvent.Type.MouseButtonRelease,
                    QPointF(2, 2), QPointF(2, 2),
                    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                ),
            )
        self.assertEqual(len(target_clicks), 1)
        self.assertEqual(outside_clicks, [])

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

    def test_hide_step_hides_border_and_mask(self):
        result = self.registry.resolve("target_btn")
        self.spotlight.show_target(result.handle, CalloutSpec("T", "B"), MockStepControls())
        self.spotlight.hide_step()
        self.assertFalse(self.spotlight._border_widget.isVisible())
        self.assertFalse(self.spotlight._top_dim.isVisible())
        self.assertFalse(self.spotlight._callout_widget.isVisible())

    def test_controls_facade_respects_safety_capabilities(self):
        facade = TourControlsFacade(StubEngine())
        self.assertTrue(facade.can_back)
        self.assertFalse(facade.can_skip)
        self.assertFalse(facade.can_next)
