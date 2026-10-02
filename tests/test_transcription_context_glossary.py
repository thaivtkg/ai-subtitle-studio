import unittest
from core.database.glossary_manager import GlossaryManager
from core.project.transcription_context import TranscriptionContext


class TestTranscriptionContextGlossary(unittest.TestCase):
    def test_normalize_source_target_pairs(self):
        ctx = TranscriptionContext(
            context="Anime battle",
            glossary=[
                " Bankai -> Giải phóng cuối cùng ",
                "Rasengan=La Toàn Hoàn",
                "bankai -> giải phóng cuối cùng",  # Duplicate check
                "Naruto",
                "",
            ],
            domain="Anime",
            lang_pair="ja-vi",
        )
        norm = ctx.normalized()
        self.assertEqual(norm.domain, "Anime")
        self.assertEqual(norm.lang_pair, "ja-vi")
        self.assertEqual(
            norm.glossary,
            [
                "Bankai -> Giải phóng cuối cùng",
                "Rasengan -> La Toàn Hoàn",
                "Naruto",
            ],
        )

    def test_load_from_glossary_db(self):
        mgr = GlossaryManager(db_path=":memory:")
        mgr.add_entry("Chidori", "Thiên Điểu", domain="Anime", lang_pair="ja-vi")
        mgr.add_entry("Kage Bunshin", "Ảnh Phân Thân", domain="Anime", lang_pair="ja-vi")
        mgr.add_entry("CPU", "Bộ xử lý", domain="IT", lang_pair="en-vi")

        ctx = TranscriptionContext(
            context="Ninja war",
            glossary=["Rasengan -> La Toàn Hoàn"],
            domain="Anime",
            lang_pair="ja-vi",
        )
        loaded = ctx.load_from_glossary_db(mgr)
        self.assertIn("Rasengan -> La Toàn Hoàn", loaded.glossary)
        self.assertIn("Chidori -> Thiên Điểu", loaded.glossary)
        self.assertIn("Kage Bunshin -> Ảnh Phân Thân", loaded.glossary)
        self.assertNotIn("CPU -> Bộ xử lý", loaded.glossary)


if __name__ == "__main__":
    unittest.main()
