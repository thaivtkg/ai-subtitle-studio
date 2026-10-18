import re
from typing import Optional
from core.database.glossary_manager import GlossaryManager
from core.translation.llm_translation_service import TranslationProviderProtocol

_LINE_PREFIX_RE = re.compile(r"^(?:[-*•]+|\d+[.)])\s*")
_LINE_SUFFIX_RE = re.compile(r"\s*(?:->|=|：|:\s).*$")
_ISO_LANGUAGE_NAMES = {
    "vi": "Vietnamese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
}

_QUOTED_TERM_RE = re.compile(r'[「『【《"\'“‘]([^」』】》"\'”’\r\n]{2,40})[」』】》"\'”’]')
_TECH_TERM_RE = re.compile(
    r"(?<![A-Za-z0-9_/])(?:"
    r"[A-Za-z]+::[A-Za-z_][A-Za-z0-9_]*"
    r"|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9_+-]*"
    r"|[A-Za-z]+(?:\+\+|#|\.js|\.py|\.net|\.ts)"
    r"|[A-Z]{2,10}(?:-\d+[A-Za-z0-9]*)?"
    r"|[A-Za-z]+\d+[A-Za-z0-9_.-]*"
    r")(?![A-Za-z0-9_/])"
)
_KATAKANA_RE = re.compile(r"[\u30a1-\u30fa\u30fc]{2,20}")
_KANJI_RE = re.compile(r"[\u4e00-\u9fff\u3005]{2,10}")
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]{2,15}")
_HANGUL_PARTICLE_SUFFIX_RE = re.compile(
    r"(?:에서|으로|에게|부터|까지|입니다|합니다|하는|이다|은|는|이|가|을|를|의|에|과|와|도)$"
)

_LATIN_CHAR = r"A-Za-zÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ0-9_"
_CAP_WORD = (
    r"[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
    r"[a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ0-9]*"
)
_PROPER_NOUN_RE = re.compile(
    rf"(?<![{_LATIN_CHAR}]){_CAP_WORD}(?:\s+{_CAP_WORD}){{0,3}}(?![{_LATIN_CHAR}])"
)

_CJK_STOPWORDS = {
    "動画", "解説", "紹介", "説明", "今回", "内容", "違い", "方法", "場合", "使用", "利用", "基本", "概要",
    "동영상", "설명", "소개", "영상", "내용", "이번", "방법", "사용",
}
_LATIN_STOPWORDS = {
    "video", "trong", "hướng", "dẫn", "giới", "thiệu", "tóm", "tắt", "nội", "dung",
    "phần", "bài", "chương", "cách", "khi", "nếu", "với", "của", "cho", "tại", "về",
    "các", "những", "một", "này", "đó", "trận", "chiến", "khám", "phá", "vùng", "đất",
    "cùng", "giữa", "lập", "trình", "quản", "lý", "bộ", "nhớ", "giải", "thích",
    "the", "this", "that", "these", "those", "in", "on", "at", "for", "with", "from",
    "by", "about", "into", "through", "after", "before", "between", "under", "over",
    "how", "what", "why", "when", "where", "who", "overview", "summary", "introduction",
    "tutorial", "guide", "episode", "part", "chapter", "and", "or",
}


def build_glossary_extraction_prompt(
    summary: str,
    video_language: str = "Auto Detect",
    domain: str = "general",
) -> str:
    cleaned_summary = (summary or "").strip()
    if not cleaned_summary:
        raise ValueError("Summary cannot be empty.")

    lang = (video_language or "").strip()
    if not lang or lang.casefold() == "auto detect":
        lang_instruction = (
            "Infer the primary spoken language of the video from the summary/context."
        )
    else:
        lang_name = _ISO_LANGUAGE_NAMES.get(lang.casefold(), lang)
        lang_instruction = f"The spoken language of the video is {lang_name}."

    dom = (domain or "").strip() or "general"

    return (
        "You are an ASR terminology specialist for Whisper speech recognition.\n"
        f"{lang_instruction}\n"
        f"Domain: {dom}\n\n"
        "Task: Based on the video summary/context below, extract the key technical terms, "
        "proper nouns, person/character names, brand names, and domain-specific vocabulary "
        "that speakers are likely to say in the video.\n"
        "Rules:\n"
        "1. Output every term in the EXACT written/spoken orthography of the video's spoken language "
        "(e.g., exact Kanji/Katakana for Japanese, exact spelling/acronyms for English) so Whisper ASR "
        "transcribes them accurately without homophone or spelling errors.\n"
        "2. Output ONLY one term per line.\n"
        "3. Do NOT include translations, explanations, numbering, bullet points, or markdown code fences.\n\n"
        f"Video Summary / Context:\n{cleaned_summary}\n"
    )


def parse_extracted_glossary(raw_response: str) -> list[str]:
    if not raw_response:
        return []

    seen: set[str] = set()
    terms: list[str] = []

    for raw_line in raw_response.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        line = _LINE_PREFIX_RE.sub("", line)
        line = _LINE_SUFFIX_RE.sub("", line).strip(" \t*`\"'")
        if not line:
            continue
        key = line.casefold()
        if key not in seen:
            seen.add(key)
            terms.append(line)

    return terms


def _term_in_summary(term_folded: str, summary_folded: str) -> bool:
    if len(term_folded) < 2:
        return False
    if all(ord(c) < 0x3000 for c in term_folded):
        return bool(
            re.search(
                rf"(?<![{_LATIN_CHAR}]){re.escape(term_folded)}(?![{_LATIN_CHAR}])",
                summary_folded,
            )
        )
    return term_folded in summary_folded


def extract_glossary_offline(
    summary: str,
    video_language: str = "Auto Detect",
    domain: str = "general",
    glossary_manager: Optional[GlossaryManager] = None,
    max_terms: int = 30,
) -> list[str]:
    cleaned_summary = (summary or "").strip()
    if not cleaned_summary:
        raise ValueError("Summary cannot be empty.")

    seen: set[str] = set()
    terms: list[str] = []

    def _add(candidate: str) -> None:
        if len(terms) >= max_terms:
            return
        val = candidate.strip(" \t.,;:!?()[]{}\"'“”‘’「」『』【】《》")
        if len(val) < 2:
            return
        key = val.casefold()
        if key in _LATIN_STOPWORDS or val in _CJK_STOPWORDS:
            return
        if key not in seen:
            seen.add(key)
            terms.append(val)

    # 1. Local SQLite GlossaryManager cross-matching
    try:
        mgr = glossary_manager if glossary_manager is not None else GlossaryManager()
        dom = (domain or "").strip() or "general"
        entries = mgr.list_entries(domain=dom)
        if dom != "general":
            entries.extend(mgr.list_entries(domain="general"))
        summary_folded = cleaned_summary.casefold()
        for entry in entries:
            src_folded = entry.source_text.casefold()
            tgt_folded = entry.target_text.casefold()
            if _term_in_summary(src_folded, summary_folded):
                _add(entry.target_text or entry.source_text)
            elif _term_in_summary(tgt_folded, summary_folded):
                _add(entry.source_text or entry.target_text)
    except Exception:
        pass

    # 2. Quoted / bracketed entities (「...」, 『...』, 【...】, "...")
    for match in _QUOTED_TERM_RE.finditer(cleaned_summary):
        _add(match.group(1))

    # 3. Technical identifiers, CamelCase, acronyms, C++, std::vector, etc.
    for match in _TECH_TERM_RE.finditer(cleaned_summary):
        _add(match.group(0))

    # 4. CJK Katakana loanwords, Kanji compounds & Korean Hangul terms
    for match in _KATAKANA_RE.finditer(cleaned_summary):
        _add(match.group(0))
    for match in _KANJI_RE.finditer(cleaned_summary):
        _add(match.group(0))
    for match in _HANGUL_RE.finditer(cleaned_summary):
        stem = _HANGUL_PARTICLE_SUFFIX_RE.sub("", match.group(0))
        _add(stem if len(stem) >= 2 else match.group(0))

    # 5. Capitalized proper nouns & multi-word names (Latin / Vietnamese / English)
    for match in _PROPER_NOUN_RE.finditer(cleaned_summary):
        words = match.group(0).split()
        while words and words[0].casefold() in _LATIN_STOPWORDS:
            words.pop(0)
        while words and words[-1].casefold() in _LATIN_STOPWORDS:
            words.pop()
        if words:
            _add(" ".join(words))

    return terms[:max_terms]


def extract_glossary_from_summary(
    provider: Optional[TranslationProviderProtocol],
    summary: str,
    video_language: str = "Auto Detect",
    domain: str = "general",
    glossary_manager: Optional[GlossaryManager] = None,
) -> list[str]:
    if provider is None:
        return extract_glossary_offline(
            summary=summary,
            video_language=video_language,
            domain=domain,
            glossary_manager=glossary_manager,
        )
    prompt = build_glossary_extraction_prompt(
        summary=summary,
        video_language=video_language,
        domain=domain,
    )
    raw_output = provider.translate(prompt)
    return parse_extracted_glossary(raw_output)

