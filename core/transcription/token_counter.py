from typing import Protocol


class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int:
        ...


class ApproximateTokenCounter:
    def count(self, text: str) -> int:
        return len(text.split()) if text.strip() else 0
