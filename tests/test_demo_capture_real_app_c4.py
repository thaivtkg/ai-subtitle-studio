import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScope,
    CaptureScenario,
    CaptureTarget,
    ExecutionMode,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.frame_clock import FrameClock
from core.demo_capture.runner import generate_one
from core.demo_capture.validation import TutorialAssetValidator
from core.runtime.runtime_paths import RuntimePaths
from ui.demo_capture.encoder import PillowAssetEncoder
from ui.demo_capture.frame_capture import FrameCaptureService
from ui.demo_capture.frame_normalizer import FrameNormalizer
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
        unrelated_preexisting = QWidget()
        unrelated_preexisting.show()
        unrelated_during = None
        try:
            with self.factory(self.scenario, ExecutionMode.REAL_APP) as (window, _, _):
                self.assertTrue(window.isVisible())
                dialog = QDialog(window)
                dialog.show()
                unrelated_during = QWidget()
                unrelated_during.show()
                self.app.processEvents()
            self.assertTrue(unrelated_preexisting.isVisible())
            self.assertTrue(unrelated_during.isVisible())
            self.assertFalse(window.isVisible())
            self.assertFalse(dialog.isVisible())
        finally:
            unrelated_preexisting.deleteLater()
            if unrelated_during is not None:
                unrelated_during.deleteLater()

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
        scenario = CaptureScenario(
            id="tc255",
            target=CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
            profile=CaptureProfile(),
            actions=(),
            output=OutputSpec("tc255.png", OutputFormat.PNG),
        )
        writer = MagicMock()
        staging = Path("test_real_app_staging")
        with self.assertRaises(CaptureRunError) as context:
            generate_one(
                scenario,
                ExecutionMode.REAL_APP,
                staging,
                writer,
                self.factory,
                FrameClock(10, time.monotonic),
                FrameCaptureService(MagicMock()),
                FrameNormalizer(),
                PillowAssetEncoder(),
                TutorialAssetValidator(),
            )
        self.assertEqual(context.exception.error_code, CaptureErrorCode.CLEANUP_FAILED)
        writer.commit.assert_not_called()
        if staging.exists():
            for path in staging.glob("*"):
                path.unlink()
            staging.rmdir()

    def test_tc256_no_attach_existing_mode(self):
        self.assertEqual(
            sorted(mode.value for mode in ExecutionMode),
            ["ISOLATED", "REAL_APP"],
        )
        self.assertNotIn("ATTACH_EXISTING", [mode.value for mode in ExecutionMode])


if __name__ == "__main__":
    unittest.main()
