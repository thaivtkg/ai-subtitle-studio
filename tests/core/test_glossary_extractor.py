import unittest

from core.transcription.glossary_extractor import (
    build_glossary_extraction_prompt,
    extract_glossary_from_summary,
    parse_extracted_glossary,
)


class StubLLMProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_prompt = None

    def translate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response_text


class TestGlossaryExtractor(unittest.TestCase):
    def test_rejects_empty_summary(self):
        with self.assertRaises(ValueError):
            build_glossary_extraction_prompt("   ", video_language="Japanese", domain="IT")

    def test_prompt_includes_summary_language_and_domain(self):
        prompt = build_glossary_extraction_prompt(
            summary="Video hướng dẫn lập trình bất đồng bộ Python với asyncio, coroutine và FastAPI",
            video_language="Japanese",
            domain="Programming",
        )
        self.assertIn("Japanese", prompt)
        self.assertIn("Programming", prompt)
        self.assertIn("asyncio", prompt)

    def test_prompt_handles_auto_detect_language(self):
        prompt = build_glossary_extraction_prompt(
            summary="医療現場におけるMRIとCTスキャンの違いについて解説する動画",
            video_language="Auto Detect",
            domain="Medical",
        )
        self.assertIn("Medical", prompt)
        self.assertIn("infer", prompt.lower())

    def test_parse_cleans_bullets_numbering_codeblocks_and_deduplicates(self):
        raw = """```text
1. 非同期処理
2) イベントループ
- コルーチン
* FastAPI
• SQLAlchemy
fastapi
  
```"""
        terms = parse_extracted_glossary(raw)
        self.assertEqual(
            terms,
            ["非同期処理", "イベントループ", "コルーチン", "FastAPI", "SQLAlchemy"],
        )

    def test_extract_glossary_end_to_end_with_provider(self):
        provider = StubLLMProvider("非同期処理\nイベントループ\nFastAPI")
        terms = extract_glossary_from_summary(
            provider=provider,
            summary="Hướng dẫn bất đồng bộ trong Python",
            video_language="Japanese",
            domain="IT",
        )
        self.assertEqual(terms, ["非同期処理", "イベントループ", "FastAPI"])
        self.assertIsNotNone(provider.last_prompt)
        self.assertIn("Japanese", provider.last_prompt)

    def test_parse_strips_explanations_and_markdown_wrappers(self):
        raw = """
- **非同期処理** -> Asynchronous processing
* `イベントループ` = Vòng lặp sự kiện
1. FastAPI: Modern Python web framework
2) コルーチン：サブルーチンの一種
"std::vector"
'16:9'
"""
        terms = parse_extracted_glossary(raw)
        self.assertEqual(
            terms,
            ["非同期処理", "イベントループ", "FastAPI", "コルーチン", "std::vector", "16:9"],
        )

    def test_parse_empty_or_whitespace_returns_empty_list(self):
        self.assertEqual(parse_extracted_glossary(""), [])
        self.assertEqual(parse_extracted_glossary("   \n  \t  "), [])

    def test_prompt_expands_iso_language_codes(self):
        prompt_ja = build_glossary_extraction_prompt(
            summary="Video hướng dẫn lập trình bất đồng bộ Python",
            video_language="ja",
            domain="IT",
        )
        self.assertIn("The spoken language of the video is Japanese", prompt_ja)

        prompt_ko = build_glossary_extraction_prompt(
            summary="Video hướng dẫn lập trình",
            video_language="ko",
            domain="IT",
        )
        self.assertIn("The spoken language of the video is Korean", prompt_ko)


if __name__ == "__main__":
    unittest.main()
