from enum import Enum
from typing import Any


class MediaImportErrorCode(str, Enum):
    INVALID_URL = "INVALID_URL"
    UNSAFE_URL = "UNSAFE_URL"
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    DRM_OR_PROTECTED = "DRM_OR_PROTECTED"
    MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
    INVALID_MEDIA = "INVALID_MEDIA"
    NO_VIDEO_STREAM = "NO_VIDEO_STREAM"
    DISK_FULL = "DISK_FULL"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    DOWNLOAD_CANCELLED = "DOWNLOAD_CANCELLED"
    FINALIZE_FAILED = "FINALIZE_FAILED"
    UNKNOWN = "UNKNOWN"


class MediaImportError(Exception):
    def __init__(
        self,
        code: MediaImportErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}
