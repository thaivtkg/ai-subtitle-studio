import unittest

from ui.theme import Theme


class ThemeTooltipTest(unittest.TestCase):
    def test_global_stylesheet_defines_high_contrast_tooltip_surface(self):
        stylesheet = Theme.get_global_stylesheet()

        self.assertIn("QToolTip", stylesheet)
        self.assertIn(f"background-color: {Theme.SURFACE_ELEVATED}", stylesheet)
        self.assertIn(f"color: {Theme.TEXT_PRIMARY}", stylesheet)
        self.assertIn(f"border: 1px solid {Theme.BORDER}", stylesheet)


if __name__ == "__main__":
    unittest.main()
