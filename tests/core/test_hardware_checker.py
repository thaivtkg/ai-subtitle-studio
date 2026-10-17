import unittest
from unittest.mock import patch, MagicMock
from core.services.hardware_checker import HardwareChecker, HardwareProfile


class TestHardwareChecker(unittest.TestCase):
    def test_detect_runs_without_error(self):
        profile = HardwareChecker.detect()
        self.assertIsInstance(profile, HardwareProfile)
        self.assertIsInstance(profile.has_cuda, bool)
        self.assertIsInstance(profile.checks, list)
        self.assertGreater(len(profile.checks), 0)
        self.assertIn(profile.recommended_model, ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"])
        self.assertIn(profile.recommended_compute, ["float16", "int8_float16", "int8"])

    @patch("torch.cuda.is_available", return_value=False)
    def test_cpu_fallback(self, _mock_cuda):
        profile = HardwareChecker.detect()
        self.assertFalse(profile.has_cuda)
        self.assertEqual(profile.recommended_compute, "int8")
        gpu_check = next(c for c in profile.checks if c["feature"] == "GPU CUDA Acceleration")
        self.assertFalse(gpu_check["can_run"])
        self.assertEqual(gpu_check["status"], "warn")

    def test_dashboard_page_has_hardware_test_buttons(self):
        from ui.pages.dashboard_page import DashboardPage
        page = DashboardPage()
        self.assertTrue(hasattr(page, "btn_auto_test"))
        self.assertTrue(hasattr(page, "btn_manual_test"))
        self.assertTrue(hasattr(page, "lbl_hw_recommendation"))
        self.assertIn("Gợi ý:", page.lbl_hw_recommendation.text())

    def test_hardware_check_dialog(self):
        from ui.dialogs.hardware_check_dialog import HardwareCheckDialog
        profile = HardwareChecker.detect()
        dialog = HardwareCheckDialog(profile=profile)
        applied = []
        dialog.apply_recommended.connect(lambda m, c: applied.append((m, c)))
        dialog._on_apply_clicked()
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0], (profile.recommended_model, profile.recommended_compute))


if __name__ == "__main__":
    unittest.main()
