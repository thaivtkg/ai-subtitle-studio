import unittest

from core.project.transcription_context import TranscriptionContext
from core.transcription.prompt_context_builder import (
    CompiledPromptContext,
    PromptContextBuilder,
)
from core.transcription.token_counter import ApproximateTokenCounter


class TestPromptContextBuilder(unittest.TestCase):
    def setUp(self):
        self.counter = ApproximateTokenCounter()
        self.builder = PromptContextBuilder(self.counter)

    def test_tc109_context_truncates_before_accepted_glossary(self):
        result = self.builder.build(
            TranscriptionContext(
                context="một hai ba bốn năm sáu bảy tám chín mười",
                glossary=["Demacia", "Lux"],
            ),
            max_tokens=6,
        )
        self.assertIn("Demacia", result.text)
        self.assertIn("Lux", result.text)
        self.assertTrue(result.context_truncated)
        self.assertTrue(result.truncated)
        self.assertEqual(result.glossary_items_dropped, 0)

    def test_tc110_glossary_over_budget_keeps_first_n_whole_terms(self):
        result = self.builder.build(
            TranscriptionContext(
                glossary=["Jarvan IV", "Demacia", "Petricite Shield"]
            ),
            max_tokens=3,
        )
        self.assertEqual(result.glossary_items_used, 1)
        self.assertEqual(result.glossary_items_dropped, 2)
        self.assertIn("Jarvan IV", result.text)
        self.assertNotIn("Demacia", result.text)
        self.assertNotIn("Petricite Shield", result.text)
        self.assertTrue(result.truncated)
        self.assertFalse(result.context_truncated)

    def test_tc111_empty_input_builds_empty_prompt(self):
        result = self.builder.build(TranscriptionContext())
        self.assertEqual(result.text, "")
        self.assertEqual(result.token_count, 0)
        self.assertFalse(result.truncated)
        self.assertFalse(result.context_truncated)
        self.assertEqual(result.glossary_items_dropped, 0)

    def test_deterministic_output(self):
        ctx = TranscriptionContext(context="Garen attack", glossary=["Demacia"])
        result1 = self.builder.build(ctx, 10)
        result2 = self.builder.build(ctx, 10)
        self.assertEqual(result1, result2)


if __name__ == "__main__":
    unittest.main()
