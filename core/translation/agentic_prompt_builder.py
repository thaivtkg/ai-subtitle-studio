import xml.sax.saxutils as saxutils
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

    def escape_xml(self, text: str) -> str:
        return saxutils.escape(text, entities={
            "'": "&apos;",
            "\"": "&quot;"
        })

    def _format_system(self, source_lang: str, target_lang: str) -> str:
        s_lang = self.escape_xml(source_lang or "Original Language")
        t_lang = self.escape_xml(target_lang or "Target Language")
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

    def _format_tm_matches(self, tm_matches: list[str]) -> str:
        if not tm_matches:
            return ""
        content = "\n".join(tm_matches)
        return f"""<tm_matches>
{content}
</tm_matches>"""

    def _format_source(self, source_text: str) -> str:
        return f"""<source_text>
{self.escape_xml(source_text)}
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
            return AgenticPromptContext(base_prompt, base_tokens, max_tokens, 0, 0, True)

        remaining_budget = max_tokens - base_tokens
        
        # 1. Inject Glossary O(N)
        accepted_glossary = []
        if glossary:
            wrapper_cost = self._token_counter.count("<glossary>\n\n</glossary>")
            remaining_budget -= wrapper_cost
            
            for term in glossary:
                escaped_term = self.escape_xml(term)
                term_cost = self._token_counter.count(escaped_term + "\n")
                if term_cost <= remaining_budget:
                    accepted_glossary.append(escaped_term)
                    remaining_budget -= term_cost
                else:
                    break
        
        glossary_final = self._format_glossary(accepted_glossary)

        # 2. Inject TM Matches O(N)
        accepted_tm = []
        if tm_matches and remaining_budget > 0:
            wrapper_cost = self._token_counter.count("<tm_matches>\n\n</tm_matches>")
            remaining_budget -= wrapper_cost
            
            for match in tm_matches:
                escaped_src = self.escape_xml(match.source_text)
                escaped_tgt = self.escape_xml(match.target_text)
                line = f'Source: "{escaped_src}" -> Target: "{escaped_tgt}"'
                
                match_cost = self._token_counter.count(line + "\n")
                if match_cost <= remaining_budget:
                    accepted_tm.append(line)
                    remaining_budget -= match_cost
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
