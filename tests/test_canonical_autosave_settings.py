import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.Gui import MainWindow
from ui.pages.settings_page import SettingsCenterPage


class CanonicalAutosaveSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_CS03_persist_setting_merges_existing_settings(self):
        window = MainWindow.__new__(MainWindow)
        with patch("ui.Gui.load_settings", return_value={"unrelated": "keep"}) as load:
            with patch("ui.Gui.save_settings") as save:
                MainWindow._persist_canonical_setting(
                    window, "canonical_auto_save_enabled", False
                )

        load.assert_called_once_with()
        save.assert_called_once_with(
            {"unrelated": "keep", "canonical_auto_save_enabled": False}
        )

    def test_CS04_settings_page_exposes_supported_delays(self):
        page = SettingsCenterPage()
        self.addCleanup(page.deleteLater)
        self.assertTrue(hasattr(page, "canonical_autosave_checkbox"))
        self.assertTrue(hasattr(page, "canonical_autosave_delay_combo"))
        self.assertEqual(
            [page.canonical_autosave_delay_combo.itemData(i) for i in range(4)],
            [500, 1000, 2000, 5000],
        )

    def test_CS05_settings_change_updates_coordinator_immediately(self):
        window = MainWindow.__new__(MainWindow)

        class Coordinator:
            def __init__(self):
                self.enabled = True
                self.delay_ms = 1000

            def set_enabled(self, value):
                self.enabled = value

            def set_delay_ms(self, value):
                self.delay_ms = value

        window.canonical_save_coordinator = Coordinator()

        class Combo:
            def itemData(self, index):
                return [500, 1000, 2000, 5000][index]

        class Page:
            canonical_autosave_delay_combo = Combo()

        window.page_settings = Page()
        with patch("ui.Gui.load_settings", return_value={}) as load:
            with patch("ui.Gui.save_settings") as save:
                MainWindow._on_canonical_autosave_enabled_changed(window, 0)
                MainWindow._on_canonical_autosave_delay_changed(window, 3)

        self.assertFalse(window.canonical_save_coordinator.enabled)
        self.assertEqual(window.canonical_save_coordinator.delay_ms, 5000)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(save.call_count, 2)


if __name__ == "__main__":
    unittest.main()
