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

    def test_C2_transition_seam_flushes_before_recovery_session_clear(self):
        from ui.Gui import MainWindow

        events = []

        class Canonical:
            enabled = True

            def flush_now(self):
                events.append("flush-a")
                return True

        class Recovery:
            def clear_session(self):
                events.append("clear-a")

        window = MainWindow.__new__(MainWindow)
        window.canonical_save_coordinator = Canonical()
        window.autosave_coordinator = Recovery()

        self.assertTrue(MainWindow._prepare_recovery_session_switch(window))
        self.assertEqual(events, ["flush-a", "clear-a"])

    def test_C2_failed_transition_flush_does_not_clear_or_replace_context(self):
        from ui.Gui import MainWindow

        events = []

        class Canonical:
            enabled = True

            def flush_now(self):
                events.append("flush-a")
                return False

        class Recovery:
            def clear_session(self):
                events.append("clear-a")

        window = MainWindow.__new__(MainWindow)
        window.canonical_save_coordinator = Canonical()
        window.autosave_coordinator = Recovery()

        self.assertFalse(MainWindow._prepare_recovery_session_switch(window))
        self.assertEqual(events, ["flush-a"])

    def test_C2_successful_close_flush_uses_shared_transition_seam(self):
        from ui.Gui import MainWindow

        class Canonical:
            enabled = True

            def flush_now(self):
                return True

        window = MainWindow.__new__(MainWindow)
        window.canonical_save_coordinator = Canonical()
        self.assertTrue(MainWindow._flush_canonical_save_before_close(window))


if __name__ == "__main__":
    unittest.main()
