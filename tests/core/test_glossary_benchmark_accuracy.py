# -*- coding: utf-8 -*-
"""QA Benchmark Accuracy Test Matrix for Glossary Extraction (Offline Context-Biasing)."""

import pytest
from core.transcription.glossary_extractor import extract_glossary_offline


def test_benchmark_case_1_tokusatsu_hero():
    """Case 1: Tokusatsu / Hero.

    Input chứa: セキュア1号, 百香, 夕夏, kèm từ リーダー, イベント, 絶望的, 世界, 友達
    Expected: セキュア1号, 百香, 夕夏, ヒーロー (hoặc role-glossary)
    Forbidden: リーダー, イベント, 絶望的, 世界, 友達
    """
    summary = (
        "セキュア1号と百香、夕夏は戦隊の仲間と共に戦う。"
        "リーダーの指示のもと、絶望的な世界で友達を守るためのイベントが展開される。"
    )
    terms = extract_glossary_offline(summary, video_language="ja")

    # Expected
    assert "セキュア1号" in terms, f"Expected 'セキュア1号' in terms: {terms}"
    assert "百香" in terms, f"Expected '百香' in terms: {terms}"
    assert "夕夏" in terms, f"Expected '夕夏' in terms: {terms}"

    # Role terms check (từ role glossary do trigger '戦隊')
    assert any(role in terms for role in ["ヒーロー", "変身", "怪人", "怪物"]), (
        f"Expected role terms in {terms}"
    )

    # Forbidden
    forbidden = ["リーダー", "イベント", "絶望的", "世界", "友達"]
    for word in forbidden:
        assert word not in terms, f"Forbidden word '{word}' found in terms: {terms}"


def test_benchmark_case_2_magical_girl():
    """Case 2: Magical Girl.

    Input chứa: セーラー戦士, Sailor Moon, カードキャプター, kèm từ アニメ, エピソード, メンバー
    Expected: セーラームーン (hoặc 変身, 先輩, 妖魔), カード (hoặc セーラー)
    Forbidden: アニメ, エピソード, メンバー
    """
    summary = (
        "人気アニメのエピソードで、セーラー戦士たちとSailor Moon、"
        "カードキャプターのメンバーが集結し、共に戦う。"
    )
    terms = extract_glossary_offline(summary, video_language="ja")

    # Expected: ít nhất một trong các danh xưng/thực thể Magical Girl
    assert any(exp in terms for exp in ["変身", "先輩", "妖魔", "魔法少女", "カード", "セーラー"]), (
        f"Expected magical girl terms in {terms}"
    )

    # Forbidden
    forbidden = ["アニメ", "エピソード", "メンバー"]
    for word in forbidden:
        assert word not in terms, f"Forbidden word '{word}' found in terms: {terms}"


def test_benchmark_case_3_tech_it():
    """Case 3: Tech / IT.

    Input chứa: std::vector, FastAPI, PyTorch, kèm từ hướng dẫn, bài học, dữ liệu
    Expected: std::vector, FastAPI, PyTorch
    Forbidden: hướng dẫn, bài học, dữ liệu
    """
    summary = (
        "Trong video hướng dẫn này, chúng tôi mang đến bài học và dữ liệu mẫu "
        "để xây dựng ứng dụng với FastAPI, PyTorch và std::vector trong C++."
    )
    terms = extract_glossary_offline(summary, video_language="vi", domain="IT")

    # Expected
    assert "std::vector" in terms, f"Expected 'std::vector' in {terms}"
    assert "FastAPI" in terms, f"Expected 'FastAPI' in {terms}"
    assert "PyTorch" in terms, f"Expected 'PyTorch' in {terms}"

    # Forbidden
    forbidden = ["hướng dẫn", "bài học", "dữ liệu"]
    for word in forbidden:
        assert word not in terms, f"Forbidden word '{word}' found in terms: {terms}"


def test_benchmark_case_4_vietnamese_sentence_initial_and_stopword_guard():
    """Case 4: Tiếng Việt hoa đầu câu.

    Input: "Hôm nay chúng ta gặp Sakura. Cô ấy biến hình tiêu diệt quái vật."
    Expected: Sakura
    Forbidden: Hôm nay, Chúng ta, Cô ấy, Biến hình (dạng từ thường nếu không force)
    """
    summary = "Hôm nay chúng ta gặp Sakura. Cô ấy biến hình tiêu diệt quái vật."
    # Khi trích xuất với video_language="ja" (âm thanh gốc của video Nhật), các đại từ/từ dừng không bị force
    terms = extract_glossary_offline(summary, video_language="ja")

    # Expected
    assert "Sakura" in terms, f"Expected 'Sakura' in {terms}"

    # Forbidden
    forbidden = ["Hôm nay", "Chúng ta", "Cô ấy", "Biến hình", "Hôm", "Cô"]
    for word in forbidden:
        assert word not in terms, f"Forbidden word '{word}' found in terms: {terms}"
