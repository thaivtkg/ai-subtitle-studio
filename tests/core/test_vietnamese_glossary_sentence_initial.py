import pytest
from core.transcription.glossary_extractor import extract_glossary_offline


def test_ac_glossary_01_filter_sentence_initial_vietnamese_stopwords():
    """AC-GLOSSARY-01: Trích xuất chuẩn tên riêng nhân vật, không bắt nhầm Bề, Bốn, Đôi, Anh đầu câu"""
    summary1 = (
        "Bề ngoài lạnh lùng nhưng nội tâm ấm áp, Lộc Minh Vu và Đoàn Hưu Minh cùng bảo vệ Điền Úc Viên."
    )
    terms1 = extract_glossary_offline(summary1, max_terms=10)
    assert "Lộc Minh Vu" in terms1
    assert "Đoàn Hưu Minh" in terms1
    assert "Điền Úc Viên" in terms1
    assert "Bề" not in terms1
    assert "Bề ngoài" not in terms1

    summary2 = (
        "Bốn năm trước tại học viện, Lâm Thư Điều tình cờ gặp gỡ Thẩm Trình và Thẩm Hòa."
    )
    terms2 = extract_glossary_offline(summary2, max_terms=10)
    assert "Lâm Thư Điều" in terms2
    assert "Thẩm Trình" in terms2
    assert "Thẩm Hòa" in terms2
    assert "Bốn" not in terms2
    assert "Bốn năm" not in terms2

    summary3 = (
        "Đôi bạn thân Tưởng Kim Tứ và Phó Bác Ngạn cùng nhau lên đường tìm kiếm Thẩm Nịch."
    )
    terms3 = extract_glossary_offline(summary3, max_terms=10)
    assert "Tưởng Kim Tứ" in terms3
    assert "Phó Bác Ngạn" in terms3
    assert "Thẩm Nịch" in terms3
    assert "Đôi" not in terms3
    assert "Đôi bạn" not in terms3


def test_glossary_sentence_initial_proper_noun_preserved_if_present_mid_sentence():
    """Tên riêng 1 từ (như Thẩm, Lộc) nếu xuất hiện ở vị trí giữa câu trong văn bản thì vẫn được giữ lại"""
    summary = "Thẩm là gia tộc lâu đời. Mọi người trong thành phố đều kính trọng nhà họ Thẩm."
    terms = extract_glossary_offline(summary, max_terms=10)
    assert "Thẩm" in terms
