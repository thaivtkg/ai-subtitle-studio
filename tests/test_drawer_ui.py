import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui.Gui import MainWindow
except (ImportError, ModuleNotFoundError):
    QApplication = None
    QTest = None
    MainWindow = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestDrawerUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window._drawer_target_width = 350
        self.window.show()

    def test_drawer_toggle_animation_and_state(self):
        dock = self.window.generation_dock
        button = self.window.btn_drawer_toggle

        self.assertTrue(dock.isVisible())
        self.assertEqual(button.text(), "›")

        QTest.mouseClick(button, Qt.LeftButton)
        QTest.qWait(500)
        self.assertFalse(dock.isVisible())
        self.assertEqual(button.text(), "‹")

        QTest.mouseClick(button, Qt.LeftButton)
        QTest.qWait(500)
        self.assertTrue(dock.isVisible())
        self.assertEqual(button.text(), "›")
        self.assertGreaterEqual(
            dock.minimumWidth(),
            350,
            "Drawer phải khôi phục chiều rộng tối thiểu có thể sử dụng.",
        )
        self.assertEqual(dock.maximumWidth(), 390)

    def test_drawer_keeps_native_title(self):
        self.assertEqual(self.window.generation_dock.windowTitle(), "AI Workspace")
        self.assertIsNone(self.window.generation_dock.titleBarWidget())

    def tearDown(self):
        self.window.close()
