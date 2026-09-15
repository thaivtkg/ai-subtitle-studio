import unittest
from pathlib import Path


class TestSubtitleAssPhaseCContracts(unittest.TestCase):
    def _ass_api(self):
        import core

        api = getattr(core, "subtitle_ass", None)
        self.assertIsNotNone(api, "ASS helper contract is missing")
        return api

    def test_ass_mapping_uses_center_alignment_and_pixel_anchor(self):
        api = self._ass_api()
        dialogue = api.build_ass_dialogue("hello", 1920, 1080, 0.25, 0.75)
        self.assertIn(r"\an5", dialogue)
        self.assertIn(r"\pos(480,810)", dialogue)

    def test_ass_escaping_has_exact_semantic_representation(self):
        api = self._ass_api()
        source = "line\n{tag}\\path"
        self.assertEqual(api.escape_ass_text(source), r"line\N\{tag\}\\path")

    def test_temporary_ass_is_cleaned_on_success_failure_and_cancel(self):
        api = self._ass_api()
        for outcome in ("success", "failure", "cancel"):
            with self.subTest(outcome=outcome):
                holder = api.temporary_ass_file("text")
                path = Path(holder.path)
                self.assertTrue(path.exists())
                holder.finish(outcome)
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
