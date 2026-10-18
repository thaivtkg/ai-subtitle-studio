import re
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


def extract_glossary_from_summary(
    provider: TranslationProviderProtocol,
    summary: str,
    video_language: str = "Auto Detect",
    domain: str = "general",
) -> list[str]:
    prompt = build_glossary_extraction_prompt(
        summary=summary,
        video_language=video_language,
        domain=domain,
    )
    raw_output = provider.translate(prompt)
    return parse_extracted_glossary(raw_output)
