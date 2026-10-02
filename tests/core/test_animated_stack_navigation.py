import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from ui.components.animated_stack import AnimatedStack


class AnimatedStackNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_returning_to_current_page_interrupts_pending_transition(self):
        stack = AnimatedStack()
        first_page = QWidget()
        second_page = QWidget()
        stack.addWidget(first_page)
        stack.addWidget(second_page)
        stack.resize(320, 200)
        stack.show()
        self.addCleanup(stack.close)
        self.app.processEvents()

        stack.setCurrentIndex(1, duration=60)
        stack.setCurrentIndex(0, duration=60)
        QTest.qWait(100)
        self.app.processEvents()

        self.assertIs(stack.currentWidget(), first_page)
        self.assertTrue(first_page.isVisible())
        self.assertFalse(second_page.isVisible())


if __name__ == "__main__":
    unittest.main()
