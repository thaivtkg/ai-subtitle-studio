from dataclasses import dataclass
from enum import Enum


class MediaImportStage(str, Enum):
    RESOLVING = "RESOLVING"
    DOWNLOADING = "DOWNLOADING"
    VALIDATING = "VALIDATING"
    FINALIZING = "FINALIZING"


@dataclass(frozen=True)
class MediaImportProgress:
    stage: MediaImportStage
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: float | None = None
    percent: float | None = None


@dataclass(frozen=True)
class MediaImportResult:
    local_path: str
    original_url: str
    filename: str
    size_bytes: int
    media_type: str
    metadata: dict[str, object]
