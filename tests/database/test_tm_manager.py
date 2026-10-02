import unittest
from core.database.tm_manager import TranslationMemoryManager, TMMatchType

class TestTranslationMemoryManager(unittest.TestCase):
    def setUp(self):
        self.mgr = TranslationMemoryManager(db_path=":memory:")

    def test_add_and_exact_match(self):
        self.mgr.add_segment(
            source_text="Hello world!",
            target_text="Chào thế giới!",
            domain="general",
            lang_pair="en-vi"
        )
        matches = self.mgr.find_matches("Hello world!", domain="general", lang_pair="en-vi")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0].match_type, TMMatchType.EXACT_100)
        self.assertEqual(matches[0].target_text, "Chào thế giới!")
        self.assertEqual(matches[0].score, 1.0)

    def test_context_match_101(self):
        self.mgr.add_segment(
            source_text="Hello",
            target_text="Xin chào",
            prev_source_text="Good morning.",
            next_source_text="How are you?"
        )
        
        matches = self.mgr.find_matches(
            "Hello",
            prev_source="Good morning.",
            next_source="How are you?"
        )
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0].match_type, TMMatchType.CONTEXT_101)
        self.assertEqual(matches[0].score, 1.0)

    def test_fuzzy_match_pruning_and_scoring(self):
        self.mgr.add_segment("She went to the store.", "Cô ấy đã đi đến cửa hàng.")
        self.mgr.add_segment("He went to the store.", "Anh ấy đã đi đến cửa hàng.")
        self.mgr.add_segment("They went to the store.", "Họ đã đi đến cửa hàng.")
        self.mgr.add_segment("Completely unrelated sentence.", "Một câu hoàn toàn không liên quan.")
        
        # Query slightly different
        matches = self.mgr.find_matches("We went to the store.", threshold=0.7)
        self.assertTrue(len(matches) >= 3)
        
        # Ensure highest match is returned as Fuzzy
        for m in matches:
            self.assertEqual(m.match_type, TMMatchType.FUZZY)
            self.assertTrue(m.score >= 0.7)
            
        # Ensure unrelated sentence is NOT matched
        matched_targets = [m.target_text for m in matches]
        self.assertNotIn("Một câu hoàn toàn không liên quan.", matched_targets)

    def test_fts5_sanitize(self):
        # Insert a sentence with special characters
        self.mgr.add_segment("What's up [dude]? *It's* a test!", "Có chuyện gì vậy anh bạn? Đây là bài kiểm tra!")
        
        # Query with special characters that could break FTS5 if not sanitized
        matches = self.mgr.find_matches("What's up [dude]? *It's* a test!")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0].match_type, TMMatchType.EXACT_100)

if __name__ == "__main__":
    unittest.main()
