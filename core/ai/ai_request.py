from dataclasses import dataclass

@dataclass
class AIRequest:
    request_id: str
    system_instruction: str
    prompt: str
    temperature: float = 0.2
    max_tokens: int = 1024