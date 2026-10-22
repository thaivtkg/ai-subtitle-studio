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

_QUOTED_TERM_RE = re.compile(
    r"「([^」\r\n]{2,40})」"
    r"|『([^』\r\n]{2,40})』"
    r"|【([^】\r\n]{2,40})】"
    r"|《([^》\r\n]{2,40})》"
    r'|"([^"\r\n]{2,40})"'
    r"|“([^”\r\n]{2,40})”"
    r"|(?<![A-Za-z0-9])'([^'\r\n]{2,40})'(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])‘([^’\r\n]{2,40})’(?![A-Za-z0-9])"
)
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
    r"(?![’'][tmdrvll]\b)"
)
_PROPER_NOUN_RE = re.compile(
    rf"(?<![{_LATIN_CHAR}]){_CAP_WORD}(?:\s+{_CAP_WORD}){{0,3}}(?![{_LATIN_CHAR}])"
)
_NEXT_LOWER_WORD_RE = re.compile(
    r"^\s+([a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ0-9_]+)"
)

_CJK_STOPWORDS = {
    "動画", "解説", "紹介", "説明", "今回", "内容", "違い", "方法", "場合", "使用", "利用", "基本", "概要",
    "동영상", "설명", "소개", "영상", "내용", "이번", "방법", "사용",
}
_BOUNDARY_STOPWORDS = {
    "video", "trong", "ngoài", "trên", "dưới", "giữa", "cùng", "với", "của", "cho",
    "tại", "từ", "đến", "tới", "về", "khi", "nếu", "vì", "do", "bởi", "để", "nhưng",
    "hoặc", "và", "hay", "các", "những", "một", "này", "đó", "chuyến", "cuộc", "buổi",
    "gặp", "đi", "the", "an", "this", "that", "these", "those", "in", "on", "at",
    "to", "for", "with", "from", "by", "about", "into", "through", "after", "before",
    "between", "under", "over", "how", "what", "why", "when", "where", "who", "it",
    "he", "she", "we", "you", "they", "let", "there", "here", "and", "or", "but",
    # Số từ & lượng từ tiếng Việt (không bao gồm tên riêng phổ biến)
    "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười",
    "trăm", "nghìn", "vạn", "đôi", "vài", "mỗi", "từng", "mọi", "nhiều", "ít",
    # Từ phương vị & vị trí
    "bề", "mặt", "phía", "bên", "trước", "sau", "đầu", "cuối",
}
_MULTIWORD_STOP_PHRASES = {
    "anh hùng", "anh em", "anh trai", "anh chàng", "dũng sĩ", "quái vật",
    "quái nhân", "yêu quái", "yêu ma", "ác ma", "ác quỷ", "ma vương",
    "ma vật", "nội dung", "hướng dẫn", "giới thiệu", "tóm tắt", "bảo vệ",
    "tiêu diệt", "giải cứu", "người dân", "dân làng", "bá tánh", "thảo dân",
    "chương trình", "chiến đấu", "chiến binh", "hiệp sĩ", "lập trình",
    "quản lý", "giải thích", "khám phá", "vùng đất", "trận chiến", "bộ nhớ",
    "nữ sinh", "nam sinh", "học sinh", "sinh viên", "thiếu nữ", "cô gái",
    "cô bé", "cậu bé", "chàng trai", "thành phố", "đô thị", "hiện đại",
    "thời đại", "siêu nhân", "siêu anh", "siêu anh hùng", "phép thuật",
    "thẻ bài", "thu phục", "biến hình", "phong ấn", "thế giới", "dị giới",
    "cổ trang", "tiên hiệp", "kiếm hiệp", "nhân vật", "câu chuyện", "bộ phim",
    "tập phim", "trò chơi", "bề ngoài", "bốn người", "bốn năm",
    "đôi bạn", "đôi bên", "anh ta", "cô ta", "chúng ta", "chúng tôi",
    "hôm nay", "ngày mai", "hôm qua",
}
_LATIN_STOPWORDS = _BOUNDARY_STOPWORDS | {
    "hướng", "dẫn", "giới", "thiệu", "tóm", "tắt", "phần", "bài", "chương",
    "cách", "trận", "khám", "phá", "vùng", "đất", "lập", "trình", "quản",
    "bộ", "nhớ", "giải", "quái", "vật", "yêu", "ma", "người", "dân", "làng",
    "tiêu", "diệt", "vệ", "cứu", "bạn", "tôi", "ta", "ngươi", "viên", "nữ",
    "học", "sinh", "thiếu", "cô", "siêu", "phố", "hiện", "thẻ", "phép",
    "thuật", "overview", "summary", "introduction", "tutorial", "guide",
    "episode", "part", "chapter", "don", "doesn", "didn", "won", "can",
    "isn", "aren", "wasn", "weren",
    # Đại từ xưng hô đơn độc
    "anh", "chị", "em", "chú", "bác", "họ", "chúng", "nó", "hắn",
}

_TECH_DOMAINS = {
    "it", "programming", "software", "tech", "medical", "finance", "science", "coding",
}

_FANTASY_STRICT_TRIGGERS = (
    "quái vật", "yêu quái", "ma vương", "ma vật", "ác ma", "ác quỷ",
    "dũng sĩ", "cổ trang", "tiên hiệp", "kiếm hiệp", "dị giới", "isekai",
    "demon king", "demon lord", "monsters", "monster", "goblin",
    "勇者", "魔王", "魔物", "怪物", "化け物", "異世界",
    "용사", "마왕", "괴물", "마물", "이세계",
)

_FANTASY_BROAD_TRIGGERS = _FANTASY_STRICT_TRIGGERS + (
    "anh hùng", "chiến binh", "hiệp sĩ", "hero", "heroes", "warrior", "knight", "fantasy",
)

_MAGICAL_GIRL_STRICT_TRIGGERS = (
    "sailor moon", "thủy thủ mặt trăng", "cardcaptor", "thủ lĩnh thẻ bài",
    "thẻ bài phép thuật", "thẻ bài clow", "clow card", "sakura card",
    "magical girl", "mahou shoujo", "precure", "pretty cure", "madoka",
    "thiếu nữ phép thuật", "nữ sinh phép thuật", "cô gái phép thuật",
    "セーラームーン", "カードキャプター", "魔法少女", "プリキュア",
    "마법소녀", "세일러문", "카드캡터",
)

_MAGICAL_GIRL_SUBJECT_HINTS = (
    "sakura", "usagi", "thủy thủ", "nữ sinh", "thiếu nữ", "cô bé",
    "さくら", "うさぎ", "女子高生",
)

_MAGICAL_GIRL_ACTION_HINTS = (
    "quái vật", "yêu ma", "yêu quái", "ác ma", "ác quỷ", "ma vương",
    "phép thuật", "biến hình", "phong ấn", "thu phục", "thẻ bài", "chiến đấu",
    "monster", "monsters", "magic", "transform", "seal",
    "妖魔", "魔物", "怪物", "変身", "封印", "魔法",
    "요마", "괴물", "마물", "변신", "봉인", "마법",
)

_MODERN_HERO_STRICT_TRIGGERS = (
    "siêu nhân", "siêu anh hùng", "kamen rider", "super sentai", "power rangers",
    "ultraman", "tokusatsu", "quái nhân", "superhero", "superheroes", "avengers",
    "spider-man", "iron man", "one punch man", "my hero academia",
    "仮面ライダー", "ウルトラマン", "スーパー戦隊", "戦隊", "怪人",
    "특촬", "가면라이더", "울트라맨", "슈퍼전대", "히어로", "괴인",
)

_MODERN_SETTING_HINTS = (
    "hiện đại", "thời hiện đại", "live action", "live-action", "người đóng",
    "đô thị", "thành phố", "học đường", "trường học", "học sinh", "sinh viên",
    "nữ sinh", "nam sinh", "cảnh sát", "quân đội", "khoa học", "công nghệ",
    "trái đất", "thế giới thực", "biến hình",
    "modern", "urban", "city", "high school", "school", "student", "police",
    "military", "sci-fi", "scifi", "earth", "transform",
    "現代", "都市", "学園", "高校", "警察", "実写", "地球", "変身",
    "现代", "都市", "学园", "真人",
    "현대", "도시", "학원", "실사",
)

_ARCHAIC_WORLD_OVERRIDES = (
    "cổ trang", "tiên hiệp", "kiếm hiệp", "dị giới", "isekai", "trung cổ",
    "medieval", "異世界", "이세계", "중세",
)

_FANTASY_ROLE_GLOSSARY: dict[str, list[str]] = {
    "vi": [
        "Ta", "Ngươi", "Nhà ngươi", "Các ngươi", "Hắn", "Bổn tọa", "Ngài",
        "Dũng sĩ", "Anh hùng", "Quái vật", "Yêu quái", "Ma vương",
        "Dân làng", "Bá tánh", "Thảo dân", "Lũ con người",
    ],
    "ja": [
        "貴様", "お前", "我", "俺様", "俺",
        "勇者", "魔王", "魔物", "怪物", "化け物",
        "勇者様", "あなた様", "私ども", "人間ども", "村人",
    ],
    "zh": [
        "本座", "吾", "汝", "尔等",
        "勇者", "魔王", "魔物", "怪物",
        "勇者大人", "恩公", "草民", "村民", "人类",
    ],
    "ko": [
        "네놈", "네녀석", "본좌", "짐",
        "용사", "마왕", "괴물", "마물",
        "용사님", "은인님", "저희", "마을 사람들", "인간들",
    ],
    "en": [
        "Thou", "Thee", "Thy", "Mortal", "Mortals",
        "Foul Beast", "Demon Lord", "Brave Hero", "My Lord", "Villagers",
    ],
}

_MAGICAL_GIRL_ROLE_GLOSSARY: dict[str, list[str]] = {
    "vi": [
        "Tiền bối", "Hậu bối", "Senpai", "Kouhai",
        "Tớ", "Cậu",
        "Biến hình", "Phép thuật", "Quái vật",
        "Em", "Chị", "Mọi người", "Ta", "Ngươi", "Các ngươi",
        "Phong ấn", "Thẻ bài", "Yêu ma", "Thủy thủ",
    ],
    "ja": [
        "先輩", "後輩", "お姉さま", "先生",
        "私", "あたし", "あなた", "あんた", "みんな", "お前",
        "妖魔", "怪物", "魔物", "魔法少女", "変身", "封印", "カード",
    ],
    "zh": [
        "学姐", "学妹", "前辈", "后辈", "老师",
        "我", "你", "你们", "大家",
        "魔法少女", "变身", "封印", "卡牌", "妖魔", "魔物", "怪物",
    ],
    "ko": [
        "선배", "후배", "선생님", "언니",
        "나", "너", "너희", "여러분",
        "마법소녀", "변신", "봉인", "카드", "요마", "괴물", "마물",
    ],
    "en": [
        "Senpai", "Kouhai", "Teacher",
        "You", "Everyone", "Magical Girl", "Transform", "Seal", "Card", "Monster", "Darkness",
    ],
}

_MODERN_HERO_ROLE_GLOSSARY: dict[str, list[str]] = {
    "vi": [
        "Ta", "Ngươi", "Các ngươi", "Lũ con người",
        "Tôi", "Chúng tôi", "Mọi người", "Người dân",
        "Siêu anh hùng", "Chiến binh", "Quái vật", "Quái nhân", "Biến hình",
    ],
    "ja": [
        "お前", "貴様", "俺", "僕", "私", "私たち", "みんな",
        "市民", "一般人", "ヒーロー", "怪人", "怪物", "変身", "人間ども",
    ],
    "zh": [
        "你", "你们", "我", "我们", "大家", "市民",
        "英雄", "超级英雄", "怪人", "怪物", "变身", "人类",
    ],
    "ko": [
        "네놈", "너희", "나", "우리", "시민",
        "히어로", "괴인", "괴물", "변신", "인간들",
    ],
    "en": [
        "You", "We", "Everyone", "Citizens", "Hero", "Superhero", "Monster", "Villain", "Transform",
    ],
}

_ROLE_GLOSSARY_BY_ARCHETYPE: dict[str, dict[str, list[str]]] = {
    "magical_girl": _MAGICAL_GIRL_ROLE_GLOSSARY,
    "modern_hero": _MODERN_HERO_ROLE_GLOSSARY,
    "archaic_fantasy": _FANTASY_ROLE_GLOSSARY,
}

_VI_DIACRITIC_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)
_JA_HINT_RE = re.compile(
    r"[\u3040-\u30ff・]|異世界|化け物|貴様|お前|俺様|私ども|人間ども|村人|「[^」]*勇者"
)


def _resolve_target_language(video_language: str, summary: str) -> str:
    lang = (video_language or "").strip().casefold()
    lang_base = re.split(r"[-_\s(]", lang)[0] if lang else ""
    if lang_base in ("vi", "vietnamese"):
        return "vi"
    if lang_base in ("ja", "jp", "japanese"):
        return "ja"
    if lang_base in ("zh", "cn", "chinese"):
        return "zh"
    if lang_base in ("ko", "kr", "korean"):
        return "ko"
    if lang_base in ("en", "english"):
        return "en"

    if _JA_HINT_RE.search(summary):
        return "ja"
    if _HANGUL_RE.search(summary):
        return "ko"
    if _KANJI_RE.search(summary):
        return "zh"
    if _VI_DIACRITIC_RE.search(summary):
        return "vi"
    return "en"


def _resolve_combat_archetype(summary_folded: str, domain: str) -> Optional[str]:
    dom_folded = (domain or "").strip().casefold()
    is_tech_domain = dom_folded in _TECH_DOMAINS
    combined_folded = f"{summary_folded} {dom_folded}".strip()

    # 1. Magical Girl (Sailor Moon, Cardcaptor Sakura, Precure, Mahou Shoujo)
    if any(_term_in_summary(t, combined_folded) for t in _MAGICAL_GIRL_STRICT_TRIGGERS):
        return "magical_girl"
    if (
        not is_tech_domain
        and any(_term_in_summary(s, summary_folded) for s in _MAGICAL_GIRL_SUBJECT_HINTS)
        and any(_term_in_summary(a, summary_folded) for a in _MAGICAL_GIRL_ACTION_HINTS)
    ):
        return "magical_girl"

    # 2. Modern Hero / Live Action / Tokusatsu (Kamen Rider, Super Sentai, Ultraman, Urban Hero)
    if any(_term_in_summary(t, combined_folded) for t in _MODERN_HERO_STRICT_TRIGGERS):
        return "modern_hero"

    triggers = _FANTASY_STRICT_TRIGGERS if is_tech_domain else _FANTASY_BROAD_TRIGGERS
    has_combat_trigger = any(_term_in_summary(t, summary_folded) for t in triggers)
    if not has_combat_trigger:
        return None

    has_archaic_override = any(_term_in_summary(a, combined_folded) for a in _ARCHAIC_WORLD_OVERRIDES)
    has_live_action = _term_in_summary("live action", combined_folded) or _term_in_summary("live-action", combined_folded) or _term_in_summary("実写", combined_folded)
    if not is_tech_domain and (
        has_live_action
        or (
            not has_archaic_override
            and any(_term_in_summary(m, combined_folded) for m in _MODERN_SETTING_HINTS)
        )
    ):
        return "modern_hero"

    return "archaic_fantasy"


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
        lang_base = re.split(r"[-_\s(]", lang.casefold())[0]
        lang_name = _ISO_LANGUAGE_NAMES.get(lang_base, lang)
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
    summary_folded = cleaned_summary.casefold()

    def _add(candidate: str) -> None:
        if len(terms) >= max_terms:
            return
        val = candidate.strip(" \t.,;:!?()[]{}\"'“”‘’「」『』【】《》")
        if len(val) < 2:
            return
        key = val.casefold()
        if key in _LATIN_STOPWORDS or key in _MULTIWORD_STOP_PHRASES or val in _CJK_STOPWORDS:
            return
        if key not in seen:
            seen.add(key)
            terms.append(val)

    def _add_forced(candidate: str) -> None:
        if len(terms) >= max_terms:
            return
        val = candidate.strip()
        if len(val) < 1:
            return
        key = val.casefold()
        if key not in seen:
            seen.add(key)
            terms.append(val)

    # 1. Genre / Archetype Role-Hierarchy Pronouns & Honorifics (Top Priority Prompt Biasing)
    archetype = _resolve_combat_archetype(summary_folded, domain)
    if archetype is not None:
        target_lang = _resolve_target_language(video_language, cleaned_summary)
        role_glossary = _ROLE_GLOSSARY_BY_ARCHETYPE.get(archetype, {})
        for role_term in role_glossary.get(target_lang, []):
            _add_forced(role_term)

    # 2. Local SQLite GlossaryManager cross-matching
    try:
        mgr = glossary_manager if glossary_manager is not None else GlossaryManager()
        dom = (domain or "").strip() or "general"
        entries = mgr.list_entries(domain=dom)
        if dom != "general":
            entries.extend(mgr.list_entries(domain="general"))
        for entry in entries:
            src_folded = entry.source_text.casefold()
            tgt_folded = entry.target_text.casefold()
            if _term_in_summary(src_folded, summary_folded):
                _add(entry.target_text or entry.source_text)
            elif _term_in_summary(tgt_folded, summary_folded):
                _add(entry.source_text or entry.target_text)
    except Exception:
        pass

    # 3. Quoted / bracketed entities (「...」, 『...』, 【...】, "...")
    for match in _QUOTED_TERM_RE.finditer(cleaned_summary):
        quoted = next((g for g in match.groups() if g), "")
        if quoted:
            _add(quoted)

    # 4. Technical identifiers, CamelCase, acronyms, C++, std::vector, etc.
    for match in _TECH_TERM_RE.finditer(cleaned_summary):
        _add(match.group(0))

    # 5. CJK Katakana loanwords, Kanji compounds & Korean Hangul terms
    for match in _KATAKANA_RE.finditer(cleaned_summary):
        _add(match.group(0))
    for match in _KANJI_RE.finditer(cleaned_summary):
        _add(match.group(0))
    for match in _HANGUL_RE.finditer(cleaned_summary):
        stem = _HANGUL_PARTICLE_SUFFIX_RE.sub("", match.group(0))
        _add(stem if len(stem) >= 2 else match.group(0))

    # 6. Capitalized proper nouns & multi-word names (Latin / Vietnamese / English)
    for match in _PROPER_NOUN_RE.finditer(cleaned_summary):
        words = match.group(0).split()
        next_word_match = _NEXT_LOWER_WORD_RE.match(cleaned_summary[match.end():])
        if next_word_match and words:
            next_word = next_word_match.group(1).casefold()
            if f"{words[-1].casefold()} {next_word}" in _MULTIWORD_STOP_PHRASES:
                words.pop()
        while words and words[0].casefold() in _BOUNDARY_STOPWORDS:
            words.pop(0)
        while words and words[-1].casefold() in _BOUNDARY_STOPWORDS:
            words.pop()
        while len(words) >= 2 and " ".join(words[:2]).casefold() in _MULTIWORD_STOP_PHRASES:
            words = words[2:]
        while len(words) >= 2 and " ".join(words[-2:]).casefold() in _MULTIWORD_STOP_PHRASES:
            words = words[:-2]
        while words and words[0].casefold() in _BOUNDARY_STOPWORDS:
            words.pop(0)
        while words and words[-1].casefold() in _BOUNDARY_STOPWORDS:
            words.pop()
        if len(words) == 1:
            single_word = words[0]
            if single_word.casefold() in _LATIN_STOPWORDS:
                continue
            # Sentence-initial guard: từ 1 chữ đứng đầu câu và theo sau là chữ thường chỉ nhận là tên riêng nếu đã đăng ký hoặc viết hoa giữa câu
            prefix = cleaned_summary[:match.start()]
            is_sentence_start = bool(re.search(r"(?:^|[.!?\n\r…])[\s\"'“”‘’«»()[\]]*$", prefix))
            next_is_lower = bool(_NEXT_LOWER_WORD_RE.match(cleaned_summary[match.end():]))
            if is_sentence_start and next_is_lower:
                sw_lower = single_word.casefold()
                is_known_trigger = (
                    sw_lower in _MAGICAL_GIRL_STRICT_TRIGGERS
                    or sw_lower in _FANTASY_BROAD_TRIGGERS
                    or (glossary_manager is not None and glossary_manager.lookup_term(single_word) is not None)
                )
                if not is_known_trigger:
                    pattern = rf"(?<![{_LATIN_CHAR}]){re.escape(single_word)}(?![{_LATIN_CHAR}])"
                    has_mid_sentence_cap = False
                    for occ in re.finditer(pattern, cleaned_summary):
                        occ_prefix = cleaned_summary[:occ.start()]
                        if not re.search(r"(?:^|[.!?\n\r…])[\s\"'“”‘’«»()[\]]*$", occ_prefix):
                            has_mid_sentence_cap = True
                            break
                    if not has_mid_sentence_cap:
                        continue
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

