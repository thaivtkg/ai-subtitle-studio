from dataclasses import dataclass
from core.database.tm_manager import TMMatch
from core.transcription.token_counter import TokenCounterProtocol

DEFAULT_TRANSLATION_BUDGET = 4000

@dataclass(frozen=True)
class AgenticPromptContext:
    prompt_text: str
    token_count: int
    max_tokens: int
    glossary_items_used: int
    tm_matches_used: int
    truncated: bool

class AgenticPromptBuilder:
    def __init__(self, token_counter: TokenCounterProtocol):
        self._token_counter = token_counter

    def _format_system(self, source_lang: str, target_lang: str) -> str:
        s_lang = source_lang or "Original Language"
        t_lang = target_lang or "Target Language"
        return f"""<system>
You are an expert subtitle translator. Translate the following subtitles from {s_lang} to {t_lang}.
Maintain the exact numbering and timing. Do not add any extra commentary or notes.
Only output the translated subtitles in standard SRT format.
</system>"""

    def _format_glossary(self, glossary: list[str]) -> str:
        if not glossary:
            return ""
        content = "\n".join(glossary)
        return f"""<glossary>
{content}
</glossary>"""

    def _format_tm_matches(self, tm_matches: list[TMMatch]) -> str:
        if not tm_matches:
            return ""
        lines = []
        for match in tm_matches:
            lines.append(f'Source: "{match.source_text}" -> Target: "{match.target_text}"')
        content = "\n".join(lines)
        return f"""<tm_matches>
{content}
</tm_matches>"""

    def _format_source(self, source_text: str) -> str:
        return f"""<source_text>
{source_text}
</source_text>"""

    def build(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary: list[str] = None,
        tm_matches: list[TMMatch] = None,
        max_tokens: int = DEFAULT_TRANSLATION_BUDGET,
    ) -> AgenticPromptContext:
        glossary = glossary or []
        tm_matches = tm_matches or []
        
        system_text = self._format_system(source_lang, target_lang)
        source_block = self._format_source(source_text)
        
        # Base prompt without any injected context
        base_prompt = f"{system_text}\n\n{source_block}"
        base_tokens = self._token_counter.count(base_prompt)
        
        if base_tokens > max_tokens:
            # Source text itself is too large (should be handled by batching earlier)
            return AgenticPromptContext(base_prompt, base_tokens, max_tokens, 0, 0, True)

        remaining_budget = max_tokens - base_tokens
        
        # 1. Inject Glossary (Highest Priority for context)
        accepted_glossary = []
        for term in glossary:
            candidate_glossary = accepted_glossary + [term]
            glossary_block = self._format_glossary(candidate_glossary)
            # Rough cost: add the new term cost, plus overhead if it's the first term
            glossary_tokens = self._token_counter.count(glossary_block)
            
            if glossary_tokens <= remaining_budget:
                accepted_glossary.append(term)
            else:
                break
                
        glossary_final = self._format_glossary(accepted_glossary)
        remaining_budget -= self._token_counter.count(glossary_final) if accepted_glossary else 0

        # 2. Inject TM Matches (Medium Priority)
        accepted_tm = []
        for match in tm_matches:
            candidate_tm = accepted_tm + [match]
            tm_block = self._format_tm_matches(candidate_tm)
            tm_tokens = self._token_counter.count(tm_block)
            
            if tm_tokens <= remaining_budget:
                accepted_tm.append(match)
            else:
                break
                
        tm_final = self._format_tm_matches(accepted_tm)
        
        # Assemble final prompt
        parts = [system_text]
        if glossary_final:
            parts.append(glossary_final)
        if tm_final:
            parts.append(tm_final)
        parts.append(source_block)
        
        final_prompt = "\n\n".join(parts)
        final_tokens = self._token_counter.count(final_prompt)
        
        truncated = len(accepted_glossary) < len(glossary) or len(accepted_tm) < len(tm_matches)
        
        return AgenticPromptContext(
            prompt_text=final_prompt,
            token_count=final_tokens,
            max_tokens=max_tokens,
            glossary_items_used=len(accepted_glossary),
            tm_matches_used=len(accepted_tm),
            truncated=truncated,
        )
