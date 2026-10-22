# -*- coding: utf-8 -*-
import pytest
from core.transcription.glossary_extractor import extract_glossary_offline


def test_ac_jap_stop_01_filter_japanese_junk_and_everyday_words():
    # AC-JAP-STOP-01: Filter junk words: counters, loanwords, truncated verbs, abstract nouns
    summary = (
        "二人と一人は100年後に日々力を合わせ、一方徐々に単独で行動した。"
        "経験浅く調子者だったが、力尽きて出会いや裏切られ仕掛けて目立たない。"
        "ドレスを着てガスやダメージを恐れず、ピンチやコンプレックスでカウンセリングやギャングを警戒。"
        "頭脳明晰な友達と少女や生徒、教官が着任し美貌や心理を担当し歓迎した。"
        "成績優秀な人気者は手先や原因の隙間を塞ぎ、配下や邪魔を排除し世界や宇宙を守る。"
        "人格や組織の壊滅、指令の状況で自由や危険を判断し敗北や精神的復讐を誓う。"
    )
    terms = extract_glossary_offline(summary, video_language="ja")

    junk_words = [
        "二人", "一人", "年後", "ドレス", "ガス", "カウンセリング", "一方", "徐々",
        "経験浅", "調子者", "力尽", "出会", "裏切", "仕掛", "目立",
        "頭脳", "友達", "少女", "世界", "ピンチ", "ギャング", "ダメージ", "コンプレックス",
        "生徒", "教官", "着任", "美貌", "心理", "担当", "歓迎", "成績優秀", "人気者",
        "手先", "原因", "隙間", "配下", "邪魔", "宇宙", "人格", "組織", "壊滅",
        "指令", "状況", "自由", "危険", "判断", "敗北", "精神", "復讐", "日々", "単独",
    ]
    for junk in junk_words:
        assert junk not in terms, f"Junk word '{junk}' should have been filtered out but was found in terms: {terms}"


def test_ac_jap_entity_01_preserve_anime_tokusatsu_magical_girl_entities():
    # AC-JAP-ENTITY-01: Preserve character and organization names
    summaries = [
        "サンエンジェルとスパンエックスはレイガーとルークスに立ち向かう。",
        "セーラーヒロイン、セーラーアクア、セーラーボルケーノ、セーラーユピテル、セーラーアスタロトが登場。"
        "イヴィルアクアとダークボルケーノ、カメラーダを百香と夕夏、果林が妖怪魔人を討伐する。",
        "セーラールーメスとセーラーアーレス、ダーティーアーレス、セーラーディウス、ダーティーディウス、インモーン、妖魔。",
        "セイントフォースのセイントグリーン、イチカと葉月メイが戦う。",
        "ディスペアーとブレコ、セキュアレンジャーが激突。",
        "セーラーフリージアとセーラーローズはダークサイドと魔王に挑む。",
        "セーラーアクアスとバルサは魔女と魔界復活計画を阻止する。",
        "ウェディングエンジェルとブラックリリー、香坂可憐と香坂翠が悪魔に立ち向かう。",
    ]

    expected_entities = [
        "サンエンジェル", "スパンエックス", "セーラーアクア", "セーラーボルケーノ",
        "セーラーアスタロト", "カメラーダ", "果林", "百香", "夕夏",
        "セイントフォース", "セーラーフリージア", "香坂可憐", "ブラックリリー",
    ]

    all_extracted_terms = []
    for s in summaries:
        all_extracted_terms.extend(extract_glossary_offline(s, video_language="ja"))

    for entity in expected_entities:
        assert entity in all_extracted_terms, f"Expected entity '{entity}' was not extracted in {all_extracted_terms}"


def test_ac_jap_numbered_01_numbered_superhero_designations():
    # AC-JAP-NUMBERED-01: Numbered superhero designations like セキュア3号, セキュア1号
    summary = "セキュアレンジャーのセキュア3号とセキュア1号がディスペアーを追撃する。"
    terms = extract_glossary_offline(summary, video_language="ja")

    assert "セキュア3号" in terms, f"Expected 'セキュア3号' in terms: {terms}"
    assert "セキュア1号" in terms, f"Expected 'セキュア1号' in terms: {terms}"
    assert "セキュア" not in terms, f"'セキュア' alone should not appear when 'セキュア3号' is present: {terms}"
