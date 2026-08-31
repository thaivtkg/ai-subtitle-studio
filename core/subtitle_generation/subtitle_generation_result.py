from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class WhisperSegmentResult:
    start_ms: int
    end_ms: int
    text: str
    words: Optional[List[Dict]] = None


@dataclass
class SubtitleGenerationResult:
    batch_id: str
    segments: List[WhisperSegmentResult]
    error: Optional[str] = None
