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
