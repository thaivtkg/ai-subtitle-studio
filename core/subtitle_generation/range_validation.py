from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional
from ui.SubEditor import time_str_to_ms


class ConflictStrategy(Enum):
    REPLACE_OVERLAP = "REPLACE_OVERLAP"
    FILL_GAPS_ONLY = "FILL_GAPS_ONLY"
    CANCEL = "CANCEL"


class RangeErrorCode(Enum):
    SUCCESS = "SUCCESS"
    
    # Input Errors
    START_INVALID = "START_INVALID"
    END_INVALID = "END_INVALID"
    START_BEYOND_END = "START_BEYOND_END"
    NEGATIVE_TIME = "NEGATIVE_TIME"
    BEYOND_VIDEO_DURATION = "BEYOND_VIDEO_DURATION"
    
    # Range Errors
    RANGE_TOO_SHORT = "RANGE_TOO_SHORT"
    RANGE_TOO_LONG_WARNING = "RANGE_TOO_LONG_WARNING"  # Recoverable warning
    
    # Runtime Errors
    GENERATION_RUNNING = "GENERATION_RUNNING"
    PROJECT_MISMATCH = "PROJECT_MISMATCH"


@dataclass
class RangeValidationResult:
    status: RangeErrorCode
    message: str
    
    # Preview metrics
    duration_ms: int = 0
    existing_subtitles_count: int = 0
    overlapping_count: int = 0
    manual_edits_count: int = 0
    generated_data_count: int = 0
    
    # Recovery suggestions
    suggested_end_ms: Optional[int] = None
    
    @property
    def is_valid(self):
        return self.status == RangeErrorCode.SUCCESS or self.status == RangeErrorCode.RANGE_TOO_LONG_WARNING


class RangeValidator:
    MIN_RANGE_MS = 50  # 50ms as per user example
    MAX_RANGE_MS = 2 * 60 * 60 * 1000  # 2 hours

    @classmethod
    def preview_range(
        cls, 
        start_ms: int, 
        end_ms: int, 
        video_duration_ms: int, 
        existing_segments: List[Dict], 
        is_generation_running: bool = False
    ) -> RangeValidationResult:
        
        # 1. Runtime failures
        if is_generation_running:
            return RangeValidationResult(
                RangeErrorCode.GENERATION_RUNNING, 
                "Generation is currently running. Please wait or cancel it."
            )
            
        # 2. Input errors
        if start_ms is None or not isinstance(start_ms, (int, float)):
            return RangeValidationResult(RangeErrorCode.START_INVALID, "Start time is invalid.")
        if end_ms is None or not isinstance(end_ms, (int, float)):
            return RangeValidationResult(RangeErrorCode.END_INVALID, "End time is invalid.")
            
        if start_ms < 0 or end_ms < 0:
            return RangeValidationResult(RangeErrorCode.NEGATIVE_TIME, "Time cannot be negative.")
            
        if start_ms >= end_ms:
            return RangeValidationResult(
                RangeErrorCode.START_BEYOND_END, 
                "Start time must be strictly less than end time."
            )
            
        if start_ms > video_duration_ms:
            return RangeValidationResult(
                RangeErrorCode.START_BEYOND_END, 
                "Start time is beyond video duration."
            )
            
        if end_ms > video_duration_ms:
            return RangeValidationResult(
                RangeErrorCode.BEYOND_VIDEO_DURATION,
                f"End time exceeds video duration ({video_duration_ms}ms).",
                suggested_end_ms=video_duration_ms
            )

        duration = int(end_ms - start_ms)
        
        # 3. Range errors
        if duration < cls.MIN_RANGE_MS:
            return RangeValidationResult(
                RangeErrorCode.RANGE_TOO_SHORT,
                f"Selected range is only {duration}ms. Please select at least {cls.MIN_RANGE_MS}ms."
            )
            
        status = RangeErrorCode.SUCCESS
        msg = "Ready to generate."
        
        if duration > cls.MAX_RANGE_MS:
            status = RangeErrorCode.RANGE_TOO_LONG_WARNING
            msg = f"Range is {duration/1000/60:.1f} minutes long. Generation will be batched."

        # 4. Subtitle Conflicts / Preview Data
        existing_count = 0
        overlapping_count = 0
        manual_edits_count = 0
        generated_data_count = 0
        
        for seg in existing_segments:
            try:
                if "start_ms" in seg:
                    seg_start = int(seg["start_ms"])
                    seg_end = int(seg["end_ms"])
                else:
                    seg_start = time_str_to_ms(seg["start"])
                    seg_end = time_str_to_ms(seg["end"])
            except (KeyError, ValueError, TypeError):
                continue
                
            # Check if segment falls within or overlaps the range
            if seg_start < end_ms and seg_end > start_ms:
                overlapping_count += 1
                if seg.get("source") == "manual":
                    manual_edits_count += 1
                else:
                    generated_data_count += 1
                    
        existing_count = len(existing_segments)
        
        return RangeValidationResult(
            status=status,
            message=msg,
            duration_ms=duration,
            existing_subtitles_count=existing_count,
            overlapping_count=overlapping_count,
            manual_edits_count=manual_edits_count,
            generated_data_count=generated_data_count
        )
