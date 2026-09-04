import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget
    from ui.toast import Toast
except (ImportError, ModuleNotFoundError):
    QApplication = None
    QWidget = None
    Toast = None


@unittest.skipIf(QApplication is None, "PySide6 is unavailable in bundled runtime")
class TestToastUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.parent.resize(800, 600)
        self.parent.show()

    def test_visible_toasts_stack_without_overlap(self):
        first = Toast(self.parent, "First")
        first.show_toast()
        second = Toast(self.parent, "Second")
        second.show_toast()

        self.assertLessEqual(second.geometry().bottom(), first.geometry().top() - 8)

    def tearDown(self):
        self.parent.close()
        self.parent.deleteLater()


if __name__ == "__main__":
    unittest.main()
