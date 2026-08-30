from dataclasses import dataclass

@dataclass
class GenerationRequest:
    request_id: str
    project_id: str
    source_fingerprint: str
    timing_artifact_id: str

    start_segment: int
    end_segment: int

    mode: str
    source_language: str
    target_language: str

    context_before: int
    context_after: int

    model_id: str
    temperature: float
    max_tokens: int