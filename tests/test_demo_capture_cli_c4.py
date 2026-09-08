import sys
import unittest
from unittest.mock import patch

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from tools.demo_capture.cli import main


class TestDemoCaptureCLIC4(unittest.TestCase):
    def test_tc236_list_returns_zero_and_no_qt(self):
        for key in list(sys.modules):
            if key.startswith("PySide6.QtWidgets"):
                del sys.modules[key]
        self.assertEqual(main(["list"]), 0)
        self.assertNotIn("PySide6.QtWidgets", sys.modules)

    def test_tc237_generate_isolated_default(self):
        with patch("tools.demo_capture.cli._do_generate", return_value=0) as generate:
            self.assertEqual(main(["generate", "demo1"]), 0)
            self.assertEqual(generate.call_args.args[0].mode, "isolated")

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
