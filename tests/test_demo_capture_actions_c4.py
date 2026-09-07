import sys
import unittest

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile, ClickAction, HoldAction, NavigateAction,
    SelectAction, SetTextAction, WaitSettledAction,
)
from ui.demo_capture.action_driver import UIActionDriver
from ui.demo_capture.navigation_adapter import CaptureNavigationAdapter


class MockResolver:
    def __init__(self):
        self.behavior = []

    def resolve_widget(self, semantic_id: str):
        result = self.behavior.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class TestDemoCaptureActionsC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.resolver = MockResolver()
        self.navigated_to = None
        self.pump_calls = 0
        self.tick_calls = 0
        self.current_time = 0.0
        self.profile = CaptureProfile()

        def mock_nav(destination):
            self.navigated_to = destination

        def mock_pump():
            self.pump_calls += 1

        def mock_tick():
            self.tick_calls += 1
            self.current_time += 0.1

        self.root = QWidget()
        self.driver = UIActionDriver(
            resolver=self.resolver,
            navigation=CaptureNavigationAdapter(mock_nav),
            event_pump=mock_pump,
            clock=lambda: self.current_time,
            capture_root=self.root,
        )
        self.tick = mock_tick

    def tearDown(self):
        self.root.deleteLater()
        self.app.processEvents()

    def test_tc200_click_semantics(self):
        btn = QPushButton()
        clicked = []
        btn.clicked.connect(lambda: clicked.append(True))
        self.resolver.behavior = [btn]
        self.driver.execute(ClickAction("btn"), self.profile, self.tick)
        self.assertTrue(clicked)
        self.assertEqual(self.pump_calls, 0)

        self.resolver.behavior = [CaptureRunError(CaptureErrorCode.TARGET_NOT_VISIBLE, "")]
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(ClickAction("btn"), self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_NOT_VISIBLE)

    def test_tc201_navigate_semantics(self):
        self.driver.execute(NavigateAction("workspace"), self.profile, self.tick)
        self.assertEqual(self.navigated_to, "workspace")
        self.assertEqual(self.pump_calls, 0)

    def test_tc202_hold_semantics(self):
        self.driver.execute(HoldAction(800), self.profile, self.tick)
        self.assertTrue(self.pump_calls > 0)
        self.assertTrue(self.tick_calls > 0)
        self.assertTrue(self.current_time >= 0.8)

    def test_tc203_set_text_semantics(self):
        line = QLineEdit("old")
        self.resolver.behavior = [line]
        self.driver.execute(SetTextAction("line", "new_text"), self.profile, self.tick)
        self.assertEqual(line.text(), "new_text")

    def test_tc204_select_semantics(self):
        combo = QComboBox()
        combo.addItem("Vietnamese", "vi")
        combo.addItem("English", "en")
        self.resolver.behavior = [combo]
        self.driver.execute(SelectAction("combo", "vi"), self.profile, self.tick)
        self.assertEqual(combo.currentData(), "vi")

        self.resolver.behavior = [combo]
        self.driver.execute(SelectAction("combo", "English"), self.profile, self.tick)
        self.assertEqual(combo.currentText(), "English")

        self.resolver.behavior = [combo]
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(SelectAction("combo", "Missing"), self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.ACTION_FAILED)

    def test_tc205_wait_settled_semantics(self):
        btn = QPushButton(parent=self.root)
        change_calls = 0

        def mutating_pump():
            nonlocal change_calls
            if change_calls < 2:
                btn.resize(100 + change_calls, 100)
                change_calls += 1
            self.pump_calls += 1

        self.driver._event_pump = mutating_pump
        self.driver.execute(WaitSettledAction(timeout_ms=3000), self.profile, self.tick)
        self.assertTrue(self.pump_calls >= 3)

        self.pump_calls = 0
        self.current_time = 0.0

        def always_mutating_pump():
            btn.resize(100 + self.pump_calls, 100)
            self.pump_calls += 1

        self.driver._event_pump = always_mutating_pump
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(WaitSettledAction(timeout_ms=500), self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.WAIT_TIMEOUT)

        self.pump_calls = 0
        self.current_time = 0.0

        def always_moving_pump():
            btn.move(10 + self.pump_calls, 10)
            self.pump_calls += 1

        self.driver._event_pump = always_moving_pump
        with self.assertRaises(CaptureRunError) as cm:
            self.driver.execute(WaitSettledAction(timeout_ms=500), self.profile, self.tick)
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.WAIT_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
