import re

from core.subtitle_validation.validation_issue import Severity, ValidationIssue
from core.subtitle_validation.validation_policy import (
    ValidationMode,
    ValidationPolicy,
    ValidationProfile,
)


class SubtitleValidator:
    @staticmethod
    def _to_ms(value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
        match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", str(value).strip())
        if not match:
            return None
        hours, minutes, seconds, millis = map(int, match.groups())
        if minutes >= 60 or seconds >= 60:
            return None
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + millis

    @staticmethod
    def validate_segment(index: int, segment: dict, video_duration_ms: int = 0,
                         mode: ValidationMode = ValidationMode.FULL_SUBTITLE,
                         profile: ValidationProfile | None = None) -> list[ValidationIssue]:
        profile = profile or ValidationProfile()
        issues = []
        raw_start, raw_end = segment.get("start"), segment.get("end")
        start = SubtitleValidator._to_ms(raw_start) if raw_start is not None else None
        end = SubtitleValidator._to_ms(raw_end) if raw_end is not None else None
        if start is None or end is None:
            return [ValidationIssue(index, Severity.ERROR, "INVALID_TIMESTAMP_FORMAT", "Định dạng thời gian không hợp lệ")]
        text = segment.get("text", "").strip()
        duration = end - start

        if start < 0:
            issues.append(ValidationIssue(index, Severity.ERROR, "INVALID_START", "Thời gian bắt đầu < 0"))
        if end <= start:
            issues.append(ValidationIssue(index, Severity.ERROR, "INVALID_RANGE", "Kết thúc <= Bắt đầu"))
        if video_duration_ms > 0 and end > video_duration_ms:
            issues.append(ValidationIssue(index, Severity.ERROR, "OUT_OF_VIDEO_RANGE", "Vượt quá thời lượng video"))

        if not text and mode == ValidationMode.FULL_SUBTITLE:
            issues.append(ValidationIssue(index, Severity.WARNING, "EMPTY_TEXT", "Phụ đề trống"))
        elif duration > 0:
            visible_text = text if profile.count_newlines_in_cps else text.replace("\r", "").replace("\n", "")
            cps = len(visible_text) / (duration / 1000.0)
            if cps > profile.max_cps:
                issues.append(
                    ValidationIssue(index, Severity.WARNING, "HIGH_CPS", f"Tốc độ đọc quá nhanh ({cps:.1f} ký tự/s)")
                )

        if profile.max_chars_per_line is not None:
            max_line_length = max((len(line) for line in text.splitlines()), default=0)
            if max_line_length > profile.max_chars_per_line:
                issues.append(
                    ValidationIssue(index, Severity.WARNING, "LINE_TOO_LONG", f"Dòng dài nhất: {max_line_length} ký tự")
                )
        if profile.max_lines is not None and len(text.splitlines()) > profile.max_lines:
            issues.append(
                ValidationIssue(index, Severity.WARNING, "TOO_MANY_LINES", f"Số dòng: {len(text.splitlines())}")
            )

        if 0 < duration < profile.min_duration_ms:
            issues.append(
                ValidationIssue(index, Severity.WARNING, "TOO_SHORT", f"Thời lượng quá ngắn (< {profile.min_duration_ms}ms)")
            )
        if duration > profile.max_duration_ms:
            issues.append(
                ValidationIssue(index, Severity.WARNING, "TOO_LONG", f"Thời lượng quá dài (> {profile.max_duration_ms}ms)")
            )
        return issues

    @staticmethod
    def validate_all(segments: list[dict], video_duration_ms: int = 0,
                     mode: ValidationMode = ValidationMode.FULL_SUBTITLE,
                     profile: ValidationProfile | None = None) -> dict[int, list[ValidationIssue]]:
        profile = profile or ValidationProfile()
        all_issues = {}
        for index, segment in enumerate(segments):
            issues = SubtitleValidator.validate_segment(index, segment, video_duration_ms, mode, profile)
            if issues:
                all_issues[index] = issues

        for index in range(len(segments) - 1):
            current_end = SubtitleValidator._to_ms(segments[index].get("end"))
            next_start = SubtitleValidator._to_ms(segments[index + 1].get("start"))
            if current_end is not None and next_start is not None and current_end > next_start:
                overlap_ms = current_end - next_start
                all_issues.setdefault(index, []).append(
                    ValidationIssue(index, profile.overlap_severity or Severity.WARNING, "OVERLAP", f"Chồng lấn {overlap_ms}ms với câu tiếp theo")
                )
                if profile.report_overlap_on_both_segments:
                    all_issues.setdefault(index + 1, []).append(
                        ValidationIssue(index + 1, profile.overlap_severity or Severity.WARNING, "OVERLAP", f"Chồng lấn {overlap_ms}ms với câu trước đó")
                    )
            elif profile.small_gap_ms is not None and 0 < next_start - current_end < profile.small_gap_ms:
                all_issues.setdefault(index, []).append(
                    ValidationIssue(index, Severity.WARNING, "SMALL_GAP", f"Khoảng cách chỉ {next_start - current_end}ms với câu tiếp theo")
                )
        return all_issues
