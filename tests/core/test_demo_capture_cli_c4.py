import sys
import time
import unittest
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureScope,
    CaptureTarget,
    OutputFormat,
    OutputSpec,
)
from core.demo_capture.registry import DemoScenarioRegistry
from tools.demo_capture.cli import main


class TestDemoCaptureCLIC4(unittest.TestCase):
    def test_tc236_list_returns_zero_and_no_qt(self):
        for key in list(sys.modules):
            if key.startswith("PySide6.QtWidgets"):
                del sys.modules[key]
        self.assertEqual(main(["list"]), 0)
        self.assertNotIn("PySide6.QtWidgets", sys.modules)

    def test_tc237_generate_isolated_default(self):
        scenario = CaptureScenario(
            "demo1",
            CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
            CaptureProfile(),
            (),
            OutputSpec("demo1.png", OutputFormat.PNG),
        )
        registry = DemoScenarioRegistry((scenario,))
        calls = []
        frame_results = []

        def probe_generate(*args):
            calls.append(args)
            window = type("Window", (), {"tour_anchor_registry": registry_marker})()
            frame_results.append(args[6].capture("target", window))
            return Path("staging") / "demo1.png"

        class FakeFactory:
            pass

        def fake_module(name, symbol, value):
            module = ModuleType(name)
            setattr(module, symbol, value)
            return module

        fake_encoder = fake_module(
            "ui.demo_capture.encoder", "PillowAssetEncoder", type("FakeEncoder", (), {})
        )
        fake_normalizer = fake_module(
            "ui.demo_capture.frame_normalizer", "FrameNormalizer", type("FakeNormalizer", (), {})
        )
        registry_marker = object()

        class FakeResolver:
            def __init__(self, registry):
                self.registry = registry

        class FakeFrameCapture:
            def __init__(self, resolver):
                self.resolver = resolver

            def capture(self, target, main_window):
                return target, main_window, self.resolver.registry

        fake_anchor_adapter = fake_module(
            "ui.demo_capture.anchor_registry_adapter",
            "AnchorRegistryCaptureAdapter",
            FakeResolver,
        )
        fake_frame_capture = fake_module(
            "ui.demo_capture.frame_capture", "FrameCaptureService", FakeFrameCapture
        )
        fake_real_package = ModuleType("ui.demo_capture.real_app")
        fake_real_package.__path__ = []

        with patch.dict(
                 sys.modules,
                 {
                     "ui.demo_capture.isolated_app_factory": fake_module(
                         "ui.demo_capture.isolated_app_factory", "IsolatedAppFactory", FakeFactory
                     ),
                     "ui.demo_capture.encoder": fake_encoder,
                     "ui.demo_capture.frame_normalizer": fake_normalizer,
                     "ui.demo_capture.anchor_registry_adapter": fake_anchor_adapter,
                     "ui.demo_capture.frame_capture": fake_frame_capture,
                 },
             ), \
             patch("tools.demo_capture.cli._get_registry", return_value=registry), \
             patch("core.demo_capture.runner.generate_one", side_effect=probe_generate):
            self.assertEqual(main(["generate", "demo1"]), 0)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1].value, "ISOLATED")
        self.assertIs(calls[0][5]._clock, time.monotonic)
        self.assertIsNotNone(calls[0][6])
        self.assertIsInstance(calls[0][4], FakeFactory)
        self.assertIs(frame_results[0][2], registry_marker)

        with patch.dict(
                 sys.modules,
                 {
                     "ui.demo_capture.real_app": fake_real_package,
                     "ui.demo_capture.real_app.real_app_capture_factory": fake_module(
                         "ui.demo_capture.real_app.real_app_capture_factory",
                         "RealAppCaptureFactory",
                         FakeFactory,
                     ),
                     "ui.demo_capture.encoder": fake_encoder,
                     "ui.demo_capture.frame_normalizer": fake_normalizer,
                     "ui.demo_capture.anchor_registry_adapter": fake_anchor_adapter,
                     "ui.demo_capture.frame_capture": fake_frame_capture,
                 },
             ), \
             patch("tools.demo_capture.cli._get_registry", return_value=registry), \
             patch("core.demo_capture.runner.generate_one", side_effect=probe_generate):
            self.assertEqual(main(["generate", "demo1", "--mode", "real"]), 0)

        self.assertEqual(calls[-1][1].value, "REAL_APP")
        self.assertIsInstance(calls[-1][4], FakeFactory)

    def test_tc238_xor_scenario_and_all(self):
        with self.assertRaises(SystemExit) as error:
            main(["generate", "foo", "--all"])
        self.assertEqual(error.exception.code, 2)
        with self.assertRaises(SystemExit) as error:
            main(["generate"])
        self.assertEqual(error.exception.code, 2)

    def test_tc239_error_mapping(self):
        for code, expected in (
            (CaptureErrorCode.ACTION_FAILED, 1),
            (CaptureErrorCode.OUTPUT_VALIDATION_FAILED, 3),
            (CaptureErrorCode.REAL_APP_ENVIRONMENT_UNAVAILABLE, 4),
        ):
            with self.subTest(code=code), patch(
                "tools.demo_capture.cli._do_generate",
                side_effect=CaptureRunError(code, ""),
            ):
                self.assertEqual(main(["generate", "demo1"]), expected)

    def test_tc240_frozen_guard(self):
        with patch("sys.frozen", True, create=True):
            self.assertEqual(main(["generate", "demo"]), 4)
            self.assertEqual(main(["list"]), 0)

    def test_tc241_isolation_from_main_bootstrap(self):
        was_loaded = "main" in sys.modules
        main(["list"])
        self.assertEqual("main" in sys.modules, was_loaded)


if __name__ == "__main__":
    unittest.main()
