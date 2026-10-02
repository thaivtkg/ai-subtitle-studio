import unittest
from core.database.tm_manager import TMMatch, TMMatchType
from core.transcription.token_counter import ApproximateTokenCounter
from core.translation.agentic_prompt_builder import AgenticPromptBuilder

class TestAgenticPromptBuilder(unittest.TestCase):
    def setUp(self):
        self.counter = ApproximateTokenCounter()
        self.builder = AgenticPromptBuilder(self.counter)

    def test_build_empty_context(self):
        ctx = self.builder.build(
            source_text="1\n00:00:10,000 --> 00:00:12,000\nHello",
            source_lang="English",
            target_lang="Vietnamese",
        )
        self.assertIn("<system>", ctx.prompt_text)
        self.assertIn("<source_text>", ctx.prompt_text)
        self.assertNotIn("<glossary>", ctx.prompt_text)
        self.assertNotIn("<tm_matches>", ctx.prompt_text)
        self.assertEqual(ctx.glossary_items_used, 0)
        self.assertEqual(ctx.tm_matches_used, 0)
        self.assertFalse(ctx.truncated)

    def test_build_with_glossary_and_tm(self):
        glossary = ["Bankai -> Giải phóng cuối cùng"]
        tm_matches = [
            TMMatch(source_text="Hello", target_text="Xin chào", match_type=TMMatchType.EXACT_100, score=1.0)
        ]
        
        ctx = self.builder.build(
            source_text="1\n00:00:10,000 --> 00:00:12,000\nHello",
            source_lang="English",
            target_lang="Vietnamese",
            glossary=glossary,
            tm_matches=tm_matches
        )
        
        self.assertIn("<glossary>", ctx.prompt_text)
        self.assertIn("Bankai -&gt; Giải phóng cuối cùng", ctx.prompt_text)
        self.assertIn("<tm_matches>", ctx.prompt_text)
        self.assertIn("Xin chào", ctx.prompt_text)
        self.assertIn("00:00:10,000 --&gt; 00:00:12,000", ctx.prompt_text)
        
        self.assertEqual(ctx.glossary_items_used, 1)
        self.assertEqual(ctx.tm_matches_used, 1)

    def test_budget_truncation(self):
        # Create a small budget that can fit system, source and 1 glossary term but not TM
        glossary = ["Term A -> Nghĩa A", "Term B -> Nghĩa B"]
        tm_matches = [
            TMMatch(source_text="Long source text 1 2 3", target_text="Long target", match_type=TMMatchType.EXACT_100, score=1.0)
        ]
        
        # Approximate tokens:
        # System: ~20 tokens
        # Source: ~6 tokens
        # Base: ~26 tokens
        # Glossary block with 1 term: ~5 tokens
        # Let's set max_tokens to 35
        
        ctx = self.builder.build(
            source_text="Hello",
            source_lang="English",
            target_lang="Vietnamese",
            glossary=glossary,
            tm_matches=tm_matches,
            max_tokens=55
        )
        
        self.assertTrue(ctx.truncated)
        self.assertTrue(ctx.token_count <= 55)
        # Should drop TM and maybe 1 glossary term
        self.assertEqual(ctx.tm_matches_used, 0)
        self.assertNotIn("<tm_matches>", ctx.prompt_text)

if __name__ == "__main__":
    unittest.main()
