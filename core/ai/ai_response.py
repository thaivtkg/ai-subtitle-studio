from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class AIResponse:
    request_id: str
    raw_text: str
    parsed_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None 