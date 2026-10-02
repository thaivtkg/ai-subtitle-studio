from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.database.glossary_manager import GlossaryManager


@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)
    domain: str = "general"
    lang_pair: str = ""

    def normalized(self) -> "TranscriptionContext":
        seen: set[str] = set()
        result: list[str] = []
        for raw in self.glossary:
            value = str(raw).strip()
            if not value:
                continue
            if "->" in value:
                parts = value.split("->", 1)
                value = f"{parts[0].strip()} -> {parts[1].strip()}"
            elif "=" in value:
                parts = value.split("=", 1)
                value = f"{parts[0].strip()} -> {parts[1].strip()}"

            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)

        return TranscriptionContext(
            context=self.context,
            glossary=result,
            domain=self.domain,
            lang_pair=self.lang_pair,
        )

    def load_from_glossary_db(
        self, manager: Optional["GlossaryManager"] = None
    ) -> "TranscriptionContext":
        if manager is None:
            from core.database.glossary_manager import GlossaryManager
            manager = GlossaryManager()

        mappings = manager.get_term_mappings(
            domain=self.domain, lang_pair=self.lang_pair or None
        )
        new_glossary = list(self.glossary)
        for src, tgt in mappings.items():
            entry_str = f"{src} -> {tgt}" if src != tgt else src
            new_glossary.append(entry_str)

        return TranscriptionContext(
            context=self.context,
            glossary=new_glossary,
            domain=self.domain,
            lang_pair=self.lang_pair,
        ).normalized()
