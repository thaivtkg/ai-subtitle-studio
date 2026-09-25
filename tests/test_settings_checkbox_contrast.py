import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.pages.settings_page import SettingsCenterPage


class SettingsCheckboxContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_disabled_unchecked_indicator_uses_intermediate_border_contrast(self):
        stylesheet = SettingsCenterPage().styleSheet()
        disabled_rule = stylesheet.split(
            'QCheckBox[settingsCheckbox="true"]::indicator:unchecked:disabled',
            1,
        )[1].split("}", 1)[0]

        self.assertIn("border: 1px solid #475569;", disabled_rule)


if __name__ == "__main__":
    unittest.main()
