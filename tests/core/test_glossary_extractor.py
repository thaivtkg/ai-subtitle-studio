import unittest

from core.database.glossary_manager import GlossaryManager
from core.transcription.glossary_extractor import (
    build_glossary_extraction_prompt,
    extract_glossary_from_summary,
    extract_glossary_offline,
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
        with self.assertRaises(ValueError):
            extract_glossary_offline("   ")

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

    def test_extract_glossary_offline_japanese_kanji_katakana_and_quotes(self):
        summary = "第1話「呪術廻戦」では、五条悟と宿儺が領域展開「無量空処」やイベントループ、FastAPIについて解説する動画です。"
        terms = extract_glossary_offline(summary, video_language="ja")
        for expected in ["呪術廻戦", "無量空処", "五条悟", "宿儺", "領域展開", "イベントループ", "FastAPI"]:
            self.assertIn(expected, terms)
        self.assertNotIn("動画", terms)
        self.assertNotIn("解説", terms)

    def test_extract_glossary_offline_latin_proper_nouns_and_tech_terms(self):
        summary = (
            "Trong video này, Nguyễn Văn A hướng dẫn lập trình FastAPI, "
            "PySide6, C++, std::vector và GraphQL tại Demacia."
        )
        terms = extract_glossary_offline(summary, video_language="vi")
        for expected in ["Nguyễn Văn A", "FastAPI", "PySide6", "C++", "std::vector", "GraphQL", "Demacia"]:
            self.assertIn(expected, terms)
        self.assertNotIn("Trong", terms)

    def test_extract_glossary_offline_matches_local_glossary_db(self):
        db = GlossaryManager(":memory:")
        db.add_entry("bất đồng bộ", "非同期処理", domain="IT")
        db.add_entry("vòng lặp sự kiện", "イベントループ", domain="IT")

        summary = "Video hướng dẫn lập trình bất đồng bộ và vòng lặp sự kiện trong Python"
        terms = extract_glossary_offline(
            summary,
            video_language="ja",
            domain="IT",
            glossary_manager=db,
        )
        self.assertIn("非同期処理", terms)
        self.assertIn("イベントループ", terms)
        self.assertIn("Python", terms)

    def test_extract_glossary_offline_db_word_boundary_prevents_substring_false_positives(self):
        db = GlossaryManager(":memory:")
        db.add_entry("AI", "人工知能", domain="IT")
        db.add_entry("IT", "情報技術", domain="IT")

        # "khai" contains "ai", "with" contains "it" -> neither should match!
        summary = "Video triển khai hệ thống with Docker"
        terms = extract_glossary_offline(
            summary,
            video_language="ja",
            domain="IT",
            glossary_manager=db,
        )
        self.assertNotIn("人工知能", terms)
        self.assertNotIn("情報技術", terms)
        self.assertIn("Docker", terms)

    def test_extract_glossary_offline_korean_hangul_and_max_terms_cap(self):
        summary = "이 동영상은 인공지능과 딥러닝 모델「트랜스포머」를 설명합니다."
        terms = extract_glossary_offline(
            summary,
            video_language="ko",
            glossary_manager=GlossaryManager(":memory:"),
        )
        self.assertIn("트랜스포머", terms)
        self.assertIn("인공지능", terms)
        self.assertIn("딥러닝", terms)
        self.assertNotIn("동영상", terms)

        long_summary = " ".join(f"Term{i}Alpha" for i in range(50))
        capped = extract_glossary_offline(
            long_summary,
            glossary_manager=GlossaryManager(":memory:"),
            max_terms=30,
        )
        self.assertEqual(len(capped), 30)

    def test_extract_glossary_from_summary_defaults_to_offline_when_provider_is_none(self):
        terms = extract_glossary_from_summary(
            provider=None,
            summary="Khám phá vùng đất Demacia cùng Garen và Lux với FastAPI",
            video_language="en",
            domain="general",
            glossary_manager=GlossaryManager(":memory:"),
        )
        for expected in ["Demacia", "Garen", "Lux", "FastAPI"]:
            self.assertIn(expected, terms)


if __name__ == "__main__":
    unittest.main()
