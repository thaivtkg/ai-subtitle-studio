import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

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


class TestDemoCaptureCIContractC4(unittest.TestCase):
    def test_tc257_tc258_ci_workflow_contracts(self):
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m tools.demo_capture validate", content)
        self.assertNotIn("tools.demo_capture generate", content)

    def test_tc259_validate_success_exit_zero_no_qapp(self):
        for name in list(sys.modules):
            if name.startswith("PySide6.QtWidgets"):
                del sys.modules[name]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGBA", (4, 3), (10, 20, 30, 255)).save(
                root / "valid.png", format="PNG"
            )
            scenario = CaptureScenario(
                "valid",
                CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
                CaptureProfile(),
                (),
                OutputSpec("valid.png", OutputFormat.PNG),
            )
            with patch("tools.demo_capture.cli._get_registry", return_value=DemoScenarioRegistry((scenario,))), \
                 patch("tools.demo_capture.cli._asset_root", return_value=root):
                self.assertEqual(main(["validate"]), 0)
        self.assertNotIn("PySide6.QtWidgets", sys.modules)

    def test_tc260_validate_fail_exit_three(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if corrupt:
                    (root / "broken.png").write_bytes(b"not a png")
                scenario = CaptureScenario(
                    "broken",
                    CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None),
                    CaptureProfile(),
                    (),
                    OutputSpec("broken.png", OutputFormat.PNG),
                )
                with patch("tools.demo_capture.cli._get_registry", return_value=DemoScenarioRegistry((scenario,))), \
                     patch("tools.demo_capture.cli._asset_root", return_value=root):
                    self.assertEqual(main(["validate"]), 3)


if __name__ == "__main__":
    unittest.main()
