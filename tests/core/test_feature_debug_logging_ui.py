import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.debug_logging import DebugConfig, debug_enabled
from ui.Gui import MainWindow


class DebugLoggingSessionControlsContracts(unittest.TestCase):
    CATEGORIES = (
        "recovery",
        "canonical_save",
        "project_switch",
        "project_status",
        "waveform",
        "artifact_sync",
    )
    CONTROL_MAP = {
        "recovery": "chk_debug_recovery",
        "canonical_save": "chk_debug_canonical_save",
        "project_switch": "chk_debug_project_switch",
        "project_status": "chk_debug_project_status",
        "waveform": "chk_debug_waveform",
        "artifact_sync": "chk_debug_artifact_sync",
    }
    MASTER_CONTROL = "chk_debug_logging_master"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        root = Path(self._temp_dir.name)
        self._save_settings = MagicMock()
        self._patchers = [
            patch(
                "ui.Gui.RuntimePaths.get_recovery_sessions_dir",
                return_value=root / "sessions",
            ),
            patch(
                "ui.Gui.RuntimePaths.get_recovery_quarantine_dir",
                return_value=root / "quarantine",
            ),
            patch(
                "ui.Gui.RuntimePaths.get_tutorial_progress_file",
                return_value=root / "tutorial_progress.json",
            ),
            patch("ui.Gui.load_settings", return_value={}),
            patch("ui.Gui.save_settings", self._save_settings),
            patch(
                "ui.subtitle_generation_panel.SubtitleGenerationPanel.check_resumable_state"
            ),
        ]
        for patcher in self._patchers:
            patcher.start()
        self._windows = []
        self.addCleanup(self._cleanup_windows)

    def _cleanup_windows(self):
        for window in reversed(self._windows):
            window.close()
            window.deleteLater()
        self.app.processEvents()
        for patcher in reversed(self._patchers):
            patcher.stop()
        self._temp_dir.cleanup()

    def _window(self):
        project_service = MagicMock()
        project_service.current_project = None
        project_service.project_dir = None
        window = MainWindow(
            project_service=project_service,
            media_import_service=MagicMock(),
        )
        self._windows.append(window)
        self.app.processEvents()
        return window

    def _settings(self, window):
        page = getattr(window, "page_settings", None)
        self.assertIsNotNone(page, "MainWindow phải có SettingsCenterPage")
        window.switch_page(6)
        self.app.processEvents()
        return page

    def _controls(self, window):
        page = self._settings(window)
        controls = {}
        for category, attribute in self.CONTROL_MAP.items():
            control = getattr(page, attribute, None)
            self.assertIsNotNone(
                control,
                f"Settings Center phải expose control {attribute} cho {category}",
            )
            controls[category] = control
        master = getattr(page, self.MASTER_CONTROL, None)
        self.assertIsNotNone(
            master,
            "Settings Center phải expose control chk_debug_logging_master",
        )
        controls["master"] = master
        return controls

    def _enable_categories(self, controls, categories):
        controls["master"].setChecked(True)
        for category in self.CATEGORIES:
            controls[category].setChecked(category in categories)

    def test_U01_fresh_session_defaults_all_controls_off(self):
        window = self._window()
        controls = self._controls(window)
        config = window._debug_config

        self.assertFalse(controls["master"].isChecked())
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                self.assertFalse(controls[category].isChecked())
                self.assertFalse(controls[category].isEnabled())
        self.assertFalse(config.master_enabled)
        self.assertEqual(config.enabled_categories, set())

    def test_U02_settings_loads_authoritative_live_config(self):
        window = self._window()
        config = window._debug_config
        config.master_enabled = True
        config.enabled_categories = {"recovery", "waveform"}

        controls = self._controls(window)
        self.assertTrue(controls["master"].isChecked())
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                self.assertEqual(
                    controls[category].isChecked(),
                    category in {"recovery", "waveform"},
                )
                self.assertTrue(controls[category].isEnabled())

    def test_U03_master_toggle_updates_runtime_config_immediately(self):
        window = self._window()
        controls = self._controls(window)

        controls["master"].setChecked(True)
        self.assertTrue(window._debug_config.master_enabled)
        controls["master"].setChecked(False)
        self.assertFalse(window._debug_config.master_enabled)

    def test_U04_each_category_control_maps_exact_locked_id(self):
        window = self._window()
        controls = self._controls(window)
        controls["master"].setChecked(True)

        for expected_category in self.CATEGORIES:
            for category in self.CATEGORIES:
                controls[category].setChecked(category == expected_category)
            with self.subTest(category=expected_category):
                self.assertEqual(
                    window._debug_config.enabled_categories,
                    {expected_category},
                )

    def test_U05_live_update_survives_navigation_without_cancel(self):
        window = self._window()
        controls = self._controls(window)
        controls["master"].setChecked(True)
        controls["recovery"].setChecked(True)

        window.switch_page(0)
        self.assertTrue(window._debug_config.master_enabled)
        self.assertEqual(window._debug_config.enabled_categories, {"recovery"})

    def test_U06_reopen_resyncs_controls_from_live_config(self):
        window = self._window()
        controls = self._controls(window)
        controls["master"].setChecked(True)
        controls["recovery"].setChecked(True)

        window.switch_page(0)
        window._debug_config.enabled_categories = {
            "artifact_sync",
            "project_switch",
        }
        window.switch_page(6)
        controls = self._controls(window)

        self.assertTrue(controls["master"].isChecked())
        self.assertEqual(
            {
                category
                for category in self.CATEGORIES
                if controls[category].isChecked()
            },
            {"artifact_sync", "project_switch"},
        )

    def test_U07a_debug_toggle_does_not_call_settings_persistence(self):
        window = self._window()
        controls = self._controls(window)
        load_calls_before = patch("ui.Gui.load_settings").start()
        self.addCleanup(load_calls_before.stop)
        save_calls_before = self._save_settings.call_count

        controls["master"].setChecked(True)
        controls["recovery"].setChecked(True)
        controls["waveform"].setChecked(True)

        self.assertEqual(load_calls_before.call_count, 0)
        self.assertEqual(self._save_settings.call_count, save_calls_before)

    def test_U08_independent_new_window_resets_debug_state(self):
        first = self._window()
        first_controls = self._controls(first)
        self._enable_categories(first_controls, {"recovery", "artifact_sync"})

        second = self._window()
        second_controls = self._controls(second)
        self.assertFalse(second._debug_config.master_enabled)
        self.assertEqual(second._debug_config.enabled_categories, set())
        self.assertFalse(second_controls["master"].isChecked())
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                self.assertFalse(second_controls[category].isChecked())

    def test_U09_toggle_takes_effect_without_restart(self):
        window = self._window()
        controls = self._controls(window)
        sink = MagicMock()
        with patch.object(window, "append_log", sink):
            window._emit_debug_event("waveform", "probe")
            controls["master"].setChecked(True)
            controls["waveform"].setChecked(True)
            window._emit_debug_event("waveform", "probe")

        debug_messages = [
            call.args[0]
            for call in sink.call_args_list
            if call.args and isinstance(call.args[0], str)
        ]
        self.assertEqual(
            [message for message in debug_messages if "[DEBUG][waveform]" in message],
            ["[DEBUG][waveform] probe"],
        )

    def test_U10_master_off_retains_category_selection_and_effective_gate(self):
        window = self._window()
        controls = self._controls(window)
        self._enable_categories(controls, {"recovery", "waveform"})

        controls["master"].setChecked(False)
        self.assertFalse(window._debug_config.master_enabled)
        self.assertEqual(
            window._debug_config.enabled_categories,
            {"recovery", "waveform"},
        )
        self.assertFalse(debug_enabled("recovery", window._debug_config))
        self.assertFalse(debug_enabled("waveform", window._debug_config))
        self.assertTrue(controls["recovery"].isChecked())
        self.assertTrue(controls["waveform"].isChecked())

        controls["master"].setChecked(True)
        self.assertTrue(debug_enabled("recovery", window._debug_config))
        self.assertTrue(debug_enabled("waveform", window._debug_config))

    def test_U11_master_off_disables_all_category_controls(self):
        window = self._window()
        controls = self._controls(window)
        self.assertFalse(controls["master"].isChecked())
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                self.assertFalse(controls[category].isEnabled())

        controls["master"].setChecked(True)
        for category in self.CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(controls[category].isEnabled())

    def test_U12_settings_entry_does_not_mutate_runtime_config(self):
        window = self._window()
        window._debug_config.master_enabled = True
        window._debug_config.enabled_categories = {
            "project_status",
            "artifact_sync",
        }
        before = (
            window._debug_config.master_enabled,
            set(window._debug_config.enabled_categories),
        )
        with patch.object(window, "_emit_debug_event") as emit:
            window.switch_page(6)

        self.assertEqual(
            (
                window._debug_config.master_enabled,
                set(window._debug_config.enabled_categories),
            ),
            before,
        )
        emit.assert_not_called()

    def test_U13_debug_toggles_do_not_trigger_business_side_effects(self):
        window = self._window()
        controls = self._controls(window)
        current_project = window.project_service.current_project
        title = window.windowTitle()
        save = MagicMock()
        with patch.object(window, "_save_current_project", save):
            self._enable_categories(controls, set(self.CATEGORIES))
            controls["master"].setChecked(False)

        self.assertIs(window.project_service.current_project, current_project)
        self.assertEqual(window.windowTitle(), title)
        save.assert_not_called()

    def test_U14_project_status_enable_is_event_based_not_snapshot_based(self):
        window = self._window()
        controls = self._controls(window)
        window._debug_config.master_enabled = True
        window._debug_config.enabled_categories = set()
        window._last_debug_project_status_state = False

        with patch.object(window, "append_log") as sink:
            window._update_window_title_dirty_marker(True)
            controls["master"].setChecked(True)
            controls["project_status"].setChecked(True)
            window._update_window_title_dirty_marker(True)
            window._update_window_title_dirty_marker(False)

        status_events = [
            call.args[0]
            for call in sink.call_args_list
            if call.args
            and isinstance(call.args[0], str)
            and call.args[0].startswith("[DEBUG][project_status]")
        ]
        self.assertEqual(len(status_events), 1)


if __name__ == "__main__":
    unittest.main()
