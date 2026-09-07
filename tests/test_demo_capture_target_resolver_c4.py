import sys
import unittest

from PySide6.QtWidgets import QApplication, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from ui.demo_capture.anchor_registry_adapter import AnchorRegistryCaptureAdapter
from ui.tutorial.anchor_registry import AnchorRegistry


class TestDemoCaptureTargetResolverC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.registry = AnchorRegistry()
        self.adapter = AnchorRegistryCaptureAdapter(self.registry)
        self.widget = QWidget()

    def tearDown(self):
        self.widget.deleteLater()
        self.app.processEvents()

    def test_tc196_resolved_returns_live_widget(self):
        self.registry.register("test.btn", self.widget)
        self.widget.show()

        resolved_widget = self.adapter.resolve_widget("test.btn")
        self.assertIs(resolved_widget, self.widget)

    def test_tc197_unsuccessful_resolution_maps_to_capture_run_error(self):
        with self.assertRaises(CaptureRunError) as cm:
            self.adapter.resolve_widget("missing.btn")
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_NOT_FOUND)

        self.registry.register("test.hidden", self.widget)
        self.widget.hide()
        with self.assertRaises(CaptureRunError) as cm:
            self.adapter.resolve_widget("test.hidden")
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_NOT_VISIBLE)

        class BadRegistry:
            def resolve(self, semantic_id):
                raise RuntimeError("Simulated crash")

        bad_adapter = AnchorRegistryCaptureAdapter(BadRegistry())
        with self.assertRaises(CaptureRunError) as cm:
            bad_adapter.resolve_widget("any.btn")
        self.assertEqual(cm.exception.error_code, CaptureErrorCode.TARGET_RESOLUTION_ERROR)


if __name__ == "__main__":
    unittest.main()
