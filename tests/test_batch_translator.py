import unittest
from unittest.mock import MagicMock
from core.translation.batch_translator import TranslationBatchWorker
from core.translation.llm_translation_service import LLMTranslationService, TranslationResult

class TestTranslationBatchWorker(unittest.TestCase):
    def setUp(self):
        self.service_mock = MagicMock(spec=LLMTranslationService)
        # Mock the token counter inside the prompt_builder
        self.service_mock.prompt_builder = MagicMock()
        self.service_mock.prompt_builder._token_counter = MagicMock()
        # Make every segment cost 500 tokens
        self.service_mock.prompt_builder._token_counter.count.return_value = 500

        self.tm_mock = MagicMock()
        self.tm_mock.find_matches.return_value = []
        
        self.glossary_mock = MagicMock()
        self.glossary_mock.get_term_mappings.return_value = {}

        self.segments = [
            {"stt": "1", "start": "00:00:01,000", "end": "00:00:02,000", "original_text": "One"},
            {"stt": "2", "start": "00:00:02,000", "end": "00:00:03,000", "original_text": "Two"},
            {"stt": "3", "start": "00:00:03,000", "end": "00:00:04,000", "original_text": "Three"},
        ]

    def test_dynamic_chunking(self):
        worker = TranslationBatchWorker(
            service=self.service_mock,
            tm_manager=self.tm_mock,
            glossary_manager=self.glossary_mock,
            segments=self.segments,
            source_lang="en",
            target_lang="vi",
            max_tokens_per_chunk=1200  # Each seg is 500. So max 2 per chunk
        )
        chunks = worker._chunk_segments_dynamic()
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 2)
        self.assertEqual(len(chunks[1]), 1)

    def test_alignment_validator_success(self):
        worker = TranslationBatchWorker(
            service=self.service_mock,
            tm_manager=self.tm_mock,
            glossary_manager=self.glossary_mock,
            segments=self.segments,
            source_lang="en",
            target_lang="vi"
        )
        
        # Valid SRT output with 3 segments
        srt_output = (
            "1\n00:00:01,000 --> 00:00:02,000\nMột\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\nHai\n\n"
            "3\n00:00:03,000 --> 00:00:04,000\nBa\n"
        )
        
        result = worker._parse_and_validate(srt_output, self.segments)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["text"], "Một")

    def test_alignment_validator_failure(self):
        worker = TranslationBatchWorker(
            service=self.service_mock,
            tm_manager=self.tm_mock,
            glossary_manager=self.glossary_mock,
            segments=self.segments,
            source_lang="en",
            target_lang="vi"
        )
        
        # Invalid SRT output with only 2 segments (LLM hallucinated/merged)
        srt_output = (
            "1\n00:00:01,000 --> 00:00:02,000\nMột và Hai\n\n"
            "3\n00:00:03,000 --> 00:00:04,000\nBa\n"
        )
        
        result = worker._parse_and_validate(srt_output, self.segments)
        self.assertIsNone(result)

    def test_fallback_and_qc(self):
        worker = TranslationBatchWorker(
            service=self.service_mock,
            tm_manager=self.tm_mock,
            glossary_manager=self.glossary_mock,
            segments=[{"stt": "1", "start": "0", "end": "1", "original_text": "Katarina is here."}],
            source_lang="en",
            target_lang="vi",
            max_retries=0  # Force immediate failure if alignment fails
        )
        
        # Mock service to return invalid alignment
        self.service_mock.translate_batch.return_value = TranslationResult(
            translated_text="1\n0\nMerged\n", # Only 1 line, will fail parsing
            prompt_context=MagicMock(),
            error=None
        )
        
        # Override run to catch signals
        emitted_chunks = []
        worker.signals.chunk_completed.connect(lambda idx, segs: emitted_chunks.append(segs))
        
        worker.run()
        
        self.assertEqual(len(emitted_chunks), 1)
        fallback_segs = emitted_chunks[0]
        self.assertEqual(fallback_segs[0]["text"], "Katarina is here.")
        self.assertIn("alignment_failed_fallback", fallback_segs[0]["metadata"]["qc_flags"])

if __name__ == "__main__":
    unittest.main()
