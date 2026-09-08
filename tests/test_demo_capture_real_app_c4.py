import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureTarget,
    ExecutionMode,
    OutputFormat,
    OutputSpec,
)
from core.runtime.runtime_paths import RuntimePaths
from ui.demo_capture.real_app.real_app_capture_factory import RealAppCaptureFactory


class TestDemoCaptureRealAppC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.scenario = CaptureScenario(
            id="tc",
            target=CaptureTarget("t"),
            profile=CaptureProfile(),
            actions=(),
            output=OutputSpec("t.gif", OutputFormat.GIF),
        )
        cls.factory = RealAppCaptureFactory()

    def test_tc251_settings_in_temp_profile(self):
        old_appdata = os.environ.get("LOCALAPPDATA")
        with self.factory(self.scenario, ExecutionMode.REAL_APP):
            current_appdata = os.environ.get("LOCALAPPDATA")
            self.assertNotEqual(current_appdata, old_appdata)
            self.assertTrue(
                str(RuntimePaths.get_user_data_dir()).startswith(current_appdata)
            )

    def test_tc252_no_main_bootstrap(self):
        with patch.dict("sys.modules", sys.modules.copy()):
            sys.modules.pop("main", None)
            with self.factory(self.scenario, ExecutionMode.REAL_APP):
                pass
            self.assertNotIn("main", sys.modules)

    def test_tc253_cleanup_owned_widgets_only(self):
        unrelated = QWidget()
        unrelated.show()
        try:
            with self.factory(self.scenario, ExecutionMode.REAL_APP) as (window, _, _):
                self.assertTrue(window.isVisible())
            self.assertTrue(unrelated.isVisible())
            self.assertFalse(window.isVisible())
        finally:
            unrelated.deleteLater()

    def test_tc254_restore_env_on_failure(self):
        old_appdata = os.environ.get("LOCALAPPDATA")
        try:
            with self.factory(self.scenario, ExecutionMode.REAL_APP):
                raise RuntimeError("Crash")
        except RuntimeError:
            pass
        self.assertEqual(os.environ.get("LOCALAPPDATA"), old_appdata)

    @patch("ui.demo_capture.real_app.real_app_session.shutil.rmtree")
    def test_tc255_cleanup_failure_blocks_commit(self, mock_rmtree):
        mock_rmtree.side_effect = OSError("Disk Error")
        with self.assertRaises(CaptureRunError) as context:
            with self.factory(self.scenario, ExecutionMode.REAL_APP):
                pass
        self.assertEqual(context.exception.error_code, CaptureErrorCode.CLEANUP_FAILED)

    def test_tc256_no_attach_existing_mode(self):
        self.assertEqual(
            sorted(mode.value for mode in ExecutionMode),
            ["ISOLATED", "REAL_APP"],
        )
        self.assertNotIn("ATTACH_EXISTING", [mode.value for mode in ExecutionMode])


if __name__ == "__main__":
    unittest.main()
