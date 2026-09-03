from dataclasses import dataclass, field


@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)

    def normalized(self) -> "TranscriptionContext":
        seen: set[str] = set()
        result: list[str] = []
        for raw in self.glossary:
            value = str(raw).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return TranscriptionContext(self.context, result)
