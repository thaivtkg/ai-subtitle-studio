import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from tools.demo_capture.cli import main


class TestDemoCaptureCIContractC4(unittest.TestCase):
    def test_tc257_tc258_ci_workflow_contracts(self):
        content = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m tools.demo_capture validate", content)
        self.assertNotIn("tools.demo_capture generate", content)

    @patch("core.demo_capture.validation.TutorialAssetValidator.validate_registry_assets")
    def test_tc259_validate_success_exit_zero_no_qapp(self, mock_validate):
        for name in list(sys.modules):
            if name.startswith("PySide6.QtWidgets"):
                del sys.modules[name]
        self.assertEqual(main(["validate"]), 0)
        self.assertNotIn("PySide6.QtWidgets", sys.modules)

    @patch("core.demo_capture.validation.TutorialAssetValidator.validate_registry_assets")
    def test_tc260_validate_fail_exit_three(self, mock_validate):
        mock_validate.side_effect = CaptureRunError(
            CaptureErrorCode.OUTPUT_VALIDATION_FAILED, ""
        )
        self.assertEqual(main(["validate"]), 3)


if __name__ == "__main__":
    unittest.main()
