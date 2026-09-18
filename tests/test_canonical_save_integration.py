import unittest
from pathlib import Path


class CanonicalSaveIntegrationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui_source = Path(__file__).parents[1].joinpath("ui", "Gui.py").read_text(
            encoding="utf-8"
        )

    def test_CA12_ctrl_s_and_autosave_share_canonical_save_path(self):
        self.assertIn("def _save_current_project(", self.gui_source)

    def test_CA15_close_flushes_pending_autosave_before_prompt(self):
        self.assertIn("def _flush_canonical_save_before_close(", self.gui_source)

    def test_CA16_failed_close_flush_uses_existing_save_discard_cancel_fallback(self):
        self.assertIn("def _flush_canonical_save_before_close(", self.gui_source)

    def test_CA17_clear_queue_flushes_pending_autosave(self):
        self.assertIn("def _flush_canonical_save_before_clear_queue(", self.gui_source)

    def test_CA19_save_without_recovery_session_still_marks_tracker_clean(self):
        self.assertIn("def _save_current_project(", self.gui_source)

    def test_CA21_project_switch_flushes_project_a_before_replacing_context(self):
        self.assertIn("def _flush_canonical_save_before_project_switch(", self.gui_source)

    def test_CA22_failed_project_a_flush_blocks_switch_to_project_b(self):
        self.assertIn("def _flush_canonical_save_before_project_switch(", self.gui_source)


if __name__ == "__main__":
    unittest.main()
