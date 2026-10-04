import sys
import unittest

from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from ui.core.design_tokens import ColorToken, RadiusToken
from ui.core.liquid_theme_engine import LiquidThemeEngine
from ui.theme import Theme


class LiquidThemeEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_compiles_without_unresolved_tokens(self):
        for wallpaper in (False, True):
            css = LiquidThemeEngine.compile_stylesheet(wallpaper=wallpaper)
            self.assertNotIn("$", css)
            self.assertIn(ColorToken.PRIMARY, css)
            self.assertIn(f"border-radius: {RadiusToken.CONTROL}px", css)

    def test_theme_aliases_follow_tokens_and_delegate(self):
        self.assertEqual(Theme.PRIMARY_PURPLE, ColorToken.PRIMARY)
        self.assertEqual(Theme.get_global_stylesheet(), LiquidThemeEngine.compile_stylesheet())

    def test_qt_parses_stylesheet_without_warnings(self):
        warnings = []
        qInstallMessageHandler(lambda t, c, m: warnings.append(m) if t != QtMsgType.QtDebugMsg else None)
        try:
            host = QWidget()
            host.setStyleSheet(LiquidThemeEngine.compile_stylesheet(wallpaper=True))
            btn = QPushButton("x", host)
            btn.setProperty("variant", "primary")
            host.show()
            host.close()
        finally:
            qInstallMessageHandler(None)
        self.assertEqual([w for w in warnings if "stylesheet" in w.lower() or "parse" in w.lower()], [])


if __name__ == "__main__":
    unittest.main()
