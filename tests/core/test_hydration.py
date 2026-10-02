import unittest
from core.subtitle_editing.hydration import hydrate_original_text

class TestHydration(unittest.TestCase):
    def setUp(self):
        # Shadow segments represent the immutable Whisper output
        self.shadow_segments = [
            {"start": 1000, "end": 2000, "text": "Exact Match Sentence."},
            {"start": 3000, "end": 5000, "text": "This is a long sentence that gets split."},
            {"start": 6000, "end": 7000, "text": "This will drift out of tolerance."},
        ]

    def test_hydration_exact_match(self):
        current_segments = [
            {"start": 1000, "end": 2000, "text": "Câu khớp hoàn toàn."}
        ]
        result = hydrate_original_text(current_segments, self.shadow_segments)
        self.assertEqual(result[0]["original_text"], "Exact Match Sentence.")

    def test_hydration_inside_match_split(self):
        # User splits the second shadow segment into two
        current_segments = [
            {"start": 3000, "end": 4000, "text": "Câu tách phần đầu."},
            {"start": 4001, "end": 5000, "text": "Câu tách phần sau."}
        ]
        result = hydrate_original_text(current_segments, self.shadow_segments)
        # Both should inherit the original text from the parent shadow segment
        self.assertEqual(result[0]["original_text"], "This is a long sentence that gets split.")
        self.assertEqual(result[1]["original_text"], "This is a long sentence that gets split.")

    def test_hydration_drift_unknown_source(self):
        # User modifies timing beyond the 100ms tolerance
        current_segments = [
            {"start": 5500, "end": 7500, "text": "Câu này đã bị thay đổi timing quá nhiều."}
        ]
        result = hydrate_original_text(current_segments, self.shadow_segments)
        self.assertEqual(result[0]["original_text"], "[Unknown Source]")
        
    def test_hydration_existing_original_text_preserved(self):
        # If original_text is already valid, do not overwrite
        current_segments = [
            {"start": 1000, "end": 2000, "text": "Câu khớp", "original_text": "Already exists!"}
        ]
        result = hydrate_original_text(current_segments, self.shadow_segments)
        self.assertEqual(result[0]["original_text"], "Already exists!")

if __name__ == "__main__":
    unittest.main()
