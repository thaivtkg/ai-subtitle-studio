import unittest
from core.database.glossary_manager import GlossaryManager, GlossaryEntry


class TestGlossaryManager(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager(db_path=":memory:")

    def test_add_and_get_entry(self):
        entry_id = self.mgr.add_entry(
            source_text="Bankai",
            target_text="Giải phóng cuối cùng",
            lang_pair="ja-vi",
            domain="Anime",
            is_case_sensitive=True,
        )
        self.assertIsInstance(entry_id, int)
        entry = self.mgr.get_entry(entry_id)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.source_text, "Bankai")
        self.assertEqual(entry.target_text, "Giải phóng cuối cùng")
        self.assertEqual(entry.lang_pair, "ja-vi")
        self.assertEqual(entry.domain, "Anime")
        self.assertTrue(entry.is_case_sensitive)

    def test_upsert_on_conflict(self):
        id1 = self.mgr.add_entry(
            source_text="Apple",
            target_text="Quả táo",
            lang_pair="en-vi",
            domain="General",
        )
        id2 = self.mgr.add_entry(
            source_text="Apple",
            target_text="Tập đoàn Apple",
            lang_pair="en-vi",
            domain="General",
        )
        # Should update existing entry, not create a duplicate
        entry = self.mgr.get_entry(id1)
        self.assertEqual(entry.target_text, "Tập đoàn Apple")
        entries = self.mgr.list_entries(domain="General")
        self.assertEqual(len(entries), 1)

    def test_list_and_filter(self):
        self.mgr.add_entry("Server", "Máy chủ", lang_pair="en-vi", domain="IT")
        self.mgr.add_entry("Database", "Cơ sở dữ liệu", lang_pair="en-vi", domain="IT")
        self.mgr.add_entry("Sharingan", "Tả Luân Nhãn", lang_pair="ja-vi", domain="Anime")

        it_entries = self.mgr.list_entries(domain="IT")
        self.assertEqual(len(it_entries), 2)

        anime_entries = self.mgr.list_entries(domain="Anime")
        self.assertEqual(len(anime_entries), 1)
        self.assertEqual(anime_entries[0].source_text, "Sharingan")

        all_entries = self.mgr.list_entries()
        self.assertEqual(len(all_entries), 3)

    def test_delete_entry(self):
        entry_id = self.mgr.add_entry("API", "Giao diện lập trình", domain="IT")
        self.assertTrue(self.mgr.delete_entry(entry_id))
        self.assertIsNone(self.mgr.get_entry(entry_id))
        self.assertFalse(self.mgr.delete_entry(entry_id))

    def test_get_term_mappings(self):
        self.mgr.add_entry("AI", "Trí tuệ nhân tạo", domain="Tech")
        self.mgr.add_entry("ML", "Học máy", domain="Tech")
        self.mgr.add_entry("Rasengan", "La Toàn Hoàn", domain="Anime")

        tech_map = self.mgr.get_term_mappings(domain="Tech")
        self.assertEqual(tech_map, {"AI": "Trí tuệ nhân tạo", "ML": "Học máy"})

    def test_batch_import_entries(self):
        raw_list = [
            {"source_text": "CPU", "target_text": "Bộ xử lý trung tâm", "domain": "Hardware"},
            {"source_text": "GPU", "target_text": "Bộ xử lý đồ họa", "domain": "Hardware"},
        ]
        count = self.mgr.import_entries(raw_list)
        self.assertEqual(count, 2)
        entries = self.mgr.list_entries(domain="Hardware")
        self.assertEqual(len(entries), 2)


if __name__ == "__main__":
    unittest.main()
