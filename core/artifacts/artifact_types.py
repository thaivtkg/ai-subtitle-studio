from enum import Enum

class ArtifactType(Enum):
    SOURCE_REFERENCE = "source_reference"
    TIMING = "timing"
    DRAFT = "draft"
    TEXT = "text"
    SUBTITLE = "subtitle"
    EXPORT = "export"
    HARDSUB = "hardsub"

class ArtifactStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"      # Bị lỗi thời (VD: Khi user sửa Timing, Draft cũ sẽ thành STALE)
    DELETED = "deleted"