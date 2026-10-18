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

    def test_extract_glossary_offline_hero_monster_pronouns_vietnamese_and_civilian_roles(self):
        summary = "Anh hùng chiến đấu với quái vật và ma vương để bảo vệ người dân trong làng"
        terms = extract_glossary_offline(
            summary,
            video_language="vi",
            domain="general",
            glossary_manager=GlossaryManager(":memory:"),
        )
        # Combat archaic/hostile pronouns (Ta - Ngươi) instead of modern (Bạn - Tôi)
        for expected in ["Ta", "Ngươi", "Các ngươi", "Ngài", "Dũng sĩ", "Quái vật", "Ma vương", "Dân làng", "Thảo dân"]:
            self.assertIn(expected, terms)
        for modern in ["Bạn", "Tôi", "Anh"]:
            self.assertNotIn(modern, terms)

    def test_extract_glossary_offline_hero_monster_pronouns_japanese_from_vietnamese_summary(self):
        summary = "Anh hùng chiến đấu với quái vật giải cứu người dân"
        terms = extract_glossary_offline(
            summary,
            video_language="ja",
            domain="Fantasy",
            glossary_manager=GlossaryManager(":memory:"),
        )
        # Japanese role pronouns: Hero/Monster (貴様, お前, 我, 俺様) vs Villager/Hero (勇者様, 私ども, 魔物, 人間ども)
        for expected in ["貴様", "お前", "我", "俺様", "勇者様", "私ども", "魔物", "怪物", "人間ども", "村人"]:
            self.assertIn(expected, terms)
        self.assertNotIn("Ta", terms)
        self.assertNotIn("Ngươi", terms)

    def test_extract_glossary_offline_hero_monster_pronouns_chinese_and_korean(self):
        summary = "Dũng sĩ tiêu diệt quái vật cứu dân làng"
        zh_terms = extract_glossary_offline(
            summary,
            video_language="zh",
            glossary_manager=GlossaryManager(":memory:"),
        )
        for expected in ["本座", "吾", "汝", "尔等", "勇者大人", "草民", "魔物"]:
            self.assertIn(expected, zh_terms)

        ko_terms = extract_glossary_offline(
            summary,
            video_language="ko",
            glossary_manager=GlossaryManager(":memory:"),
        )
        for expected in ["네놈", "본좌", "용사님", "저희", "괴물", "마물", "인간들"]:
            self.assertIn(expected, ko_terms)

    def test_extract_glossary_offline_does_not_false_trigger_fantasy_pronouns_on_tech_summary(self):
        # "chiến đấu" with bugs or "hero4" in an IT tutorial must NOT inject Ta/Ngươi/Ma vương
        summary = "Lập trình viên chiến đấu với bug trên GoPro Hero4 bằng FastAPI và Docker"
        terms = extract_glossary_offline(
            summary,
            video_language="vi",
            domain="IT",
            glossary_manager=GlossaryManager(":memory:"),
        )
        self.assertIn("FastAPI", terms)
        self.assertIn("Docker", terms)
        self.assertNotIn("Ngươi", terms)
        self.assertNotIn("Ma vương", terms)
        self.assertNotIn("Thảo dân", terms)

    def test_vietnamese_multiword_proper_names_and_places_preserved(self):
        db = GlossaryManager(":memory:")
        names = [
            "Hà Nội",
            "Nguyễn Văn Dũng",
            "Lê Văn Anh",
            "Phạm Minh Vương",
            "Hùng Vương",
            "Lý Thường Kiệt",
            "Nguyễn Thị Dung",
            "Nguyễn Thị Bảo",
            "Trần Quốc Chiến",
            "Thích Nhất Hạnh",
        ]
        for name in names:
            terms = extract_glossary_offline(
                f"Chuyến đi tới gặp {name} trong video này.",
                video_language="vi",
                glossary_manager=db,
            )
            self.assertIn(name, terms, f"Expected full proper name '{name}' in {terms}")
            self.assertNotIn("Chuyến", terms)

    def test_english_contractions_and_possessives_do_not_corrupt_quotes_or_proper_nouns(self):
        db = GlossaryManager(":memory:")
        summary = "Don't worry, it's a FastAPI tutorial about Garen's sword and 'Shadowblade'."
        terms = extract_glossary_offline(
            summary,
            video_language="en",
            glossary_manager=db,
        )
        self.assertIn("FastAPI", terms)
        self.assertIn("Garen", terms)
        self.assertIn("Shadowblade", terms)
        self.assertNotIn("t worry, it", terms)
        self.assertNotIn("Don", terms)

    def test_resolve_target_language_handles_kanji_only_japanese_and_locale_codes(self):
        db = GlossaryManager(":memory:")
        # Kanji-only Japanese with Japanese punctuation/triggers under Auto Detect
        ja_auto_terms = extract_glossary_offline(
            "「勇者」・魔王・異世界",
            video_language="Auto Detect",
            glossary_manager=db,
        )
        self.assertIn("貴様", ja_auto_terms)
        self.assertIn("勇者様", ja_auto_terms)

        # Locale code like "ja-JP" with Vietnamese summary
        ja_locale_terms = extract_glossary_offline(
            "Anh hùng diệt quái vật",
            video_language="ja-JP",
            glossary_manager=db,
        )
        self.assertIn("貴様", ja_locale_terms)
        self.assertNotIn("Ngươi", ja_locale_terms)

    def test_extract_glossary_offline_magical_girl_sailor_moon_and_sakura(self):
        db = GlossaryManager(":memory:")
        summary = "Nữ sinh Sailor Moon và Sakura chiến đấu với quái vật và thu phục thẻ bài phép thuật"

        vi_terms = extract_glossary_offline(
            summary,
            video_language="vi",
            glossary_manager=db,
        )
        for expected in ["Sailor Moon", "Sakura", "Ta", "Ngươi", "Tớ", "Cậu", "Em", "Chị", "Mọi người", "Biến hình", "Phong ấn", "Thẻ bài"]:
            self.assertIn(expected, vi_terms)
        for archaic in ["Bổn tọa", "Thảo dân", "Bá tánh", "Dân làng"]:
            self.assertNotIn(archaic, vi_terms)

        ja_terms = extract_glossary_offline(
            summary,
            video_language="ja",
            glossary_manager=db,
        )
        for expected in ["私", "あたし", "あなた", "みんな", "お前", "妖魔", "魔法少女", "変身", "封印"]:
            self.assertIn(expected, ja_terms)
        for archaic_or_rough in ["俺様", "我", "勇者様", "村人"]:
            self.assertNotIn(archaic_or_rough, ja_terms)

    def test_extract_glossary_offline_modern_hero_and_live_action_tokusatsu(self):
        db = GlossaryManager(":memory:")
        summary = "Anh hùng chiến đấu với quái vật ở thời hiện đại live action để bảo vệ người dân thành phố cùng Kamen Rider"

        vi_terms = extract_glossary_offline(
            summary,
            video_language="vi",
            glossary_manager=db,
        )
        for expected in ["Kamen Rider", "Ta", "Ngươi", "Các ngươi", "Tôi", "Chúng tôi", "Mọi người", "Người dân", "Siêu anh hùng", "Quái nhân", "Biến hình"]:
            self.assertIn(expected, vi_terms)
        for archaic in ["Bổn tọa", "Thảo dân", "Bá tánh", "Dân làng"]:
            self.assertNotIn(archaic, vi_terms)

        ja_terms = extract_glossary_offline(
            summary,
            video_language="ja",
            glossary_manager=db,
        )
        for expected in ["お前", "貴様", "俺", "僕", "私", "私たち", "みんな", "市民", "一般人", "ヒーロー", "怪人", "変身"]:
            self.assertIn(expected, ja_terms)
        for archaic in ["勇者様", "村人", "私ども"]:
            self.assertNotIn(archaic, ja_terms)

        en_terms = extract_glossary_offline(
            summary,
            video_language="en",
            glossary_manager=db,
        )
        for expected in ["Hero", "Superhero", "Monster", "Villain", "Citizens", "Transform"]:
            self.assertIn(expected, en_terms)
        for archaic in ["Thou", "Thee", "Thy", "Villagers"]:
            self.assertNotIn(archaic, en_terms)

    def test_sakura_without_combat_or_magic_context_does_not_false_trigger_role_glossary(self):
        db = GlossaryManager(":memory:")
        summary = "Chuyến đi ngắm hoa Sakura tại Tokyo vào mùa xuân"
        terms = extract_glossary_offline(
            summary,
            video_language="vi",
            glossary_manager=db,
        )
        self.assertIn("Sakura", terms)
        self.assertIn("Tokyo", terms)
        for unwanted in ["Ngươi", "Yêu ma", "Phong ấn", "Biến hình", "Bổn tọa"]:
            self.assertNotIn(unwanted, terms)


if __name__ == "__main__":
    unittest.main()


