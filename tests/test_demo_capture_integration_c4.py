import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QPushButton

from core.demo_capture.artifact_writer import ArtifactWriter
from core.demo_capture.frame_clock import FrameClock
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureScope,
    CaptureTarget,
    ClickAction,
    ExecutionMode,
    HoldAction,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.runner import generate_one
from core.demo_capture.validation import TutorialAssetValidator
from ui.demo_capture.anchor_registry_adapter import AnchorRegistryCaptureAdapter
from ui.demo_capture.encoder import PillowAssetEncoder
from ui.demo_capture.frame_capture import FrameCaptureService
from ui.demo_capture.frame_normalizer import FrameNormalizer
from ui.demo_capture.isolated_app_factory import IsolatedAppFactory


class RealFrameCaptureAdapter:
    def capture(self, target, main_window):
        resolver = AnchorRegistryCaptureAdapter(main_window.tour_anchor_registry)
        return FrameCaptureService(resolver).capture(target, main_window)


class TestDemoCaptureIntegrationC4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.asset_root = Path("test_integration_assets")
        self.staging_dir = self.asset_root / ".staging"
        self.asset_root.mkdir(exist_ok=True)
        self.staging_dir.mkdir(exist_ok=True)
        self.writer = ArtifactWriter(self.asset_root)
        self.validator = TutorialAssetValidator()
        self.encoder = PillowAssetEncoder()
        self.normalizer = FrameNormalizer()
        self.frame_capture = RealFrameCaptureAdapter()
        self.factory = IsolatedAppFactory()

    def tearDown(self):
        shutil.rmtree(self.asset_root, ignore_errors=True)

    def _make_test_factory(self, mutate_fn=None, observed_windows=None):
        @contextmanager
        def test_factory(scenario, mode):
            with self.factory(scenario, mode) as (win, driver, resolver):
                if observed_windows is not None:
                    observed_windows.append(win)
                button = QPushButton("Target", win)
                button.resize(100, 50)
                button.move(200, 200)
                button.show()
                win.tour_anchor_registry.register("test.btn", button)
                if mutate_fn:
                    mutate_fn(button)
                yield win, driver, resolver

        return test_factory

    def test_tc247_real_target_region_png(self):
        scenario = CaptureScenario(
            id="tc247",
            target=CaptureTarget("test.btn", padding=16),
            profile=CaptureProfile(window_size=(800, 600)),
            actions=(),
            output=OutputSpec("tc247.png", OutputFormat.PNG),
        )

        observed_windows = []
        out_path = generate_one(
            scenario,
            ExecutionMode.ISOLATED,
            self.staging_dir,
            self.writer,
            self._make_test_factory(observed_windows=observed_windows),
            FrameClock(scenario.profile.fps, time.monotonic),
            self.frame_capture,
            self.normalizer,
            self.encoder,
            self.validator,
        )

        self.assertTrue(out_path.exists())
        self.assertEqual(observed_windows[0].size().width(), 800)
        self.assertEqual(observed_windows[0].size().height(), 600)
        self.assertIsInstance(observed_windows[0].project_service, MagicMock)
        self.assertIsInstance(observed_windows[0].media_import_service, MagicMock)
        with Image.open(out_path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (132, 82))

    def test_tc248_real_animated_gif_with_transition(self):
        scenario = CaptureScenario(
            id="tc248",
            target=CaptureTarget("test.btn", padding=0),
            profile=CaptureProfile(window_size=(800, 600), fps=10),
            actions=(ClickAction("test.btn"), HoldAction(300)),
            output=OutputSpec("tc248.gif", OutputFormat.GIF),
        )

        def mutate(button):
            button.clicked.connect(lambda: button.resize(200, 100))

        out_path = generate_one(
            scenario,
            ExecutionMode.ISOLATED,
            self.staging_dir,
            self.writer,
            self._make_test_factory(mutate),
            FrameClock(scenario.profile.fps, time.monotonic),
            self.frame_capture,
            self.normalizer,
            self.encoder,
            self.validator,
        )

        self.assertTrue(out_path.exists())
        with Image.open(out_path) as image:
            self.assertEqual(image.format, "GIF")
            self.assertGreaterEqual(image.n_frames, 2)
            self.assertEqual(image.size, (200, 100))

    def test_tc249_isolated_no_os_interaction(self):
        automation_modules = {name for name in sys.modules if name.split(".")[0] in {
            "pyautogui", "pynput", "keyboard", "mouse"
        }}
        scenario = CaptureScenario(
            id="tc249",
            target=CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
            profile=CaptureProfile(),
            actions=(),
            output=OutputSpec("tc249.png", OutputFormat.PNG),
        )

        generate_one(
            scenario,
            ExecutionMode.ISOLATED,
            self.staging_dir,
            self.writer,
            self.factory,
            FrameClock(10, time.monotonic),
            self.frame_capture,
            self.normalizer,
            self.encoder,
            self.validator,
        )
        self.assertEqual(
            automation_modules,
            {name for name in sys.modules if name.split(".")[0] in {
                "pyautogui", "pynput", "keyboard", "mouse"
            }},
        )

    def test_tc250_profile_isolation(self):
        profiles = []
        original_localappdata = os.environ.get("LOCALAPPDATA")

        with tempfile.TemporaryDirectory() as user_profile:
            user_root = Path(user_profile) / "AI Subtitle Studio"
            (user_root / "recovery").mkdir(parents=True)
            (user_root / "settings.json").write_bytes(b"settings-sentinel")
            (user_root / "tutorial_progress.json").write_bytes(b"progress-sentinel")
            (user_root / "recovery" / "state.bin").write_bytes(b"recovery-sentinel")
            before = {
                path.relative_to(user_root): path.read_bytes()
                for path in user_root.rglob("*")
                if path.is_file()
            }

            @contextmanager
            def spy_factory(scenario, mode):
                with self.factory(scenario, mode) as (win, driver, resolver):
                    profiles.append(os.environ.get("LOCALAPPDATA"))
                    yield win, driver, resolver

            scenario = CaptureScenario(
                id="tc250",
                target=CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
                profile=CaptureProfile(),
                actions=(),
                output=OutputSpec("tc250.png", OutputFormat.PNG),
            )

            with patch.dict(os.environ, {"LOCALAPPDATA": user_profile}):
                for _ in range(2):
                    generate_one(
                        scenario,
                        ExecutionMode.ISOLATED,
                        self.staging_dir,
                        self.writer,
                        spy_factory,
                        FrameClock(10, time.monotonic),
                        self.frame_capture,
                        self.normalizer,
                        self.encoder,
                        self.validator,
                    )

                after = {
                    path.relative_to(user_root): path.read_bytes()
                    for path in user_root.rglob("*")
                    if path.is_file()
                }

        self.assertEqual(len(profiles), 2)
        self.assertNotEqual(profiles[0], profiles[1])
        self.assertEqual(before, after)
        self.assertEqual(os.environ.get("LOCALAPPDATA"), original_localappdata)


if __name__ == "__main__":
    unittest.main()
