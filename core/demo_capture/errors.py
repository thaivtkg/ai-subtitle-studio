from enum import Enum
from typing import Optional


class CaptureErrorCode(str, Enum):
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_NOT_VISIBLE = "TARGET_NOT_VISIBLE"
    TARGET_INVALID = "TARGET_INVALID"
    TARGET_RESOLUTION_ERROR = "TARGET_RESOLUTION_ERROR"
    WAIT_TIMEOUT = "WAIT_TIMEOUT"
    ACTION_FAILED = "ACTION_FAILED"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    ENCODE_FAILED = "ENCODE_FAILED"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
    WRITE_FAILED = "WRITE_FAILED"
    REAL_APP_ENVIRONMENT_UNAVAILABLE = "REAL_APP_ENVIRONMENT_UNAVAILABLE"
    REAL_APP_OWNERSHIP_FAILED = "REAL_APP_OWNERSHIP_FAILED"
    DESKTOP_INTERACTION_FAILED = "DESKTOP_INTERACTION_FAILED"
    CLEANUP_FAILED = "CLEANUP_FAILED"
    INVALID_SCENARIO = "INVALID_SCENARIO"
    ASSET_INVALID = "ASSET_INVALID"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    ARTIFACT_COMMIT_FAILED = "ARTIFACT_COMMIT_FAILED"


class CaptureRunError(Exception):
    def __init__(
        self,
        error_code: CaptureErrorCode,
        message: str,
        scenario_id: Optional[str] = None,
        action_index: Optional[int] = None,
        action_kind: Optional[str] = None,
        target: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.scenario_id = scenario_id
        self.action_index = action_index
        self.action_kind = action_kind
        self.target = target
