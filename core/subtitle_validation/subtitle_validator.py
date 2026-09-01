import re

from core.subtitle_validation.validation_issue import Severity, ValidationIssue
from core.subtitle_validation.validation_policy import ValidationPolicy


class SubtitleValidator:
    @staticmethod
    def _to_ms(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(value).strip())
        if not match:
            return 0
        hours, minutes, seconds, millis = map(int, match.groups())
        if minutes >= 60 or seconds >= 60:
            return 0
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + millis

    @staticmethod
    def validate_segment(index: int, segment: dict, video_duration_ms: int = 0) -> list[ValidationIssue]:
        issues = []
        start = SubtitleValidator._to_ms(segment.get("start", 0))
        end = SubtitleValidator._to_ms(segment.get("end", 0))
        text = segment.get("text", "").strip()
        duration = end - start

        if start < 0:
            issues.append(ValidationIssue(index, Severity.ERROR, "INVALID_START", "Thời gian bắt đầu < 0"))
        if end <= start:
            issues.append(ValidationIssue(index, Severity.ERROR, "INVALID_RANGE", "Kết thúc <= Bắt đầu"))
        if video_duration_ms > 0 and end > video_duration_ms:
            issues.append(ValidationIssue(index, Severity.ERROR, "OUT_OF_VIDEO_RANGE", "Vượt quá thời lượng video"))

        if not text:
            issues.append(ValidationIssue(index, Severity.WARNING, "EMPTY_TEXT", "Phụ đề trống"))
        elif duration > 0:
            cps = len(text) / (duration / 1000.0)
            if cps > ValidationPolicy.MAX_CPS:
                issues.append(
                    ValidationIssue(index, Severity.WARNING, "HIGH_CPS", f"Tốc độ đọc quá nhanh ({cps:.1f} ký tự/s)")
                )

        if 0 < duration < ValidationPolicy.MIN_DURATION_MS:
            issues.append(
                ValidationIssue(index, Severity.WARNING, "TOO_SHORT", f"Thời lượng quá ngắn (< {ValidationPolicy.MIN_DURATION_MS}ms)")
            )
        if duration > ValidationPolicy.MAX_DURATION_MS:
            issues.append(
                ValidationIssue(index, Severity.WARNING, "TOO_LONG", f"Thời lượng quá dài (> {ValidationPolicy.MAX_DURATION_MS}ms)")
            )
        return issues

    @staticmethod
    def validate_all(segments: list[dict], video_duration_ms: int = 0) -> dict[int, list[ValidationIssue]]:
        all_issues = {}
        for index, segment in enumerate(segments):
            issues = SubtitleValidator.validate_segment(index, segment, video_duration_ms)
            if issues:
                all_issues[index] = issues

        for index in range(len(segments) - 1):
            current_end = SubtitleValidator._to_ms(segments[index].get("end", 0))
            next_start = SubtitleValidator._to_ms(segments[index + 1].get("start", 0))
            if current_end > next_start:
                overlap_ms = current_end - next_start
                all_issues.setdefault(index, []).append(
                    ValidationIssue(index, Severity.WARNING, "OVERLAP", f"Chồng lấn {overlap_ms}ms với câu tiếp theo")
                )
                all_issues.setdefault(index + 1, []).append(
                    ValidationIssue(index + 1, Severity.WARNING, "OVERLAP", f"Chồng lấn {overlap_ms}ms với câu trước đó")
                )
        return all_issues
