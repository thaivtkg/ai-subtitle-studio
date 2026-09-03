import re
from dataclasses import dataclass

from core.project.transcription_context import TranscriptionContext
from core.transcription.token_counter import TokenCounterProtocol


DEFAULT_PROMPT_BUDGET = 180


@dataclass(frozen=True)
class CompiledPromptContext:
    text: str
    token_count: int
    max_tokens: int
    glossary_items_used: int
    glossary_items_dropped: int
    context_truncated: bool
    truncated: bool


class PromptContextBuilder:
    def __init__(self, token_counter: TokenCounterProtocol):
        self._token_counter = token_counter

    def _compose_prompt(self, glossary: list[str], context: str) -> str:
        parts = []
        if glossary:
            parts.append(f"Terminology: {', '.join(glossary)}.")
        if context:
            parts.append(f"Context: {context}")
        return " ".join(parts).strip()

    def build(
        self,
        transcription_context: TranscriptionContext,
        max_tokens: int = DEFAULT_PROMPT_BUDGET,
    ) -> CompiledPromptContext:
        normalized = transcription_context.normalized()
        if not normalized.context and not normalized.glossary:
            return CompiledPromptContext("", 0, max_tokens, 0, 0, False, False)

        accepted_glossary = []
        for term in normalized.glossary:
            candidate = self._compose_prompt(accepted_glossary + [term], "")
            if self._token_counter.count(candidate) <= max_tokens:
                accepted_glossary.append(term)
            else:
                break

        glossary_dropped = len(normalized.glossary) - len(accepted_glossary)
        full_context = normalized.context.strip()
        accepted_context = ""
        context_truncated = False

        if full_context:
            candidate = self._compose_prompt(accepted_glossary, full_context)
            if self._token_counter.count(candidate) <= max_tokens:
                accepted_context = full_context
            else:
                context_truncated = True
                accepted_context = self._truncate_context(
                    accepted_glossary, full_context, max_tokens
                )

        final_text = self._compose_prompt(accepted_glossary, accepted_context)
        return CompiledPromptContext(
            text=final_text,
            token_count=self._token_counter.count(final_text),
            max_tokens=max_tokens,
            glossary_items_used=len(accepted_glossary),
            glossary_items_dropped=glossary_dropped,
            context_truncated=context_truncated,
            truncated=glossary_dropped > 0 or context_truncated,
        )

    def _truncate_context(
        self, accepted_glossary: list[str], full_context: str, max_tokens: int
    ) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", full_context)
        if len(sentences) > 1:
            for i in range(len(sentences) - 1, 0, -1):
                prefix = " ".join(sentences[:i])
                if self._token_counter.count(
                    self._compose_prompt(accepted_glossary, prefix)
                ) <= max_tokens:
                    return prefix

        words = full_context.split()
        if len(words) > 1:
            for i in range(len(words) - 1, 0, -1):
                prefix = " ".join(words[:i])
                if self._token_counter.count(
                    self._compose_prompt(accepted_glossary, prefix)
                ) <= max_tokens:
                    return prefix

        for i in range(len(full_context) - 1, 0, -1):
            prefix = full_context[:i]
            if self._token_counter.count(
                self._compose_prompt(accepted_glossary, prefix)
            ) <= max_tokens:
                return prefix
        return ""
