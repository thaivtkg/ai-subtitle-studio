import copy
from dataclasses import dataclass
from enum import Enum, auto

from core.subtitle_validation.subtitle_validator import SubtitleValidator
from core.subtitle_validation.validation_issue import Severity
from core.subtitle_validation.validation_policy import ValidationProfile


class QualitySeverity(Enum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class QualityIssue:
    subtitle_index: int
    rule_id: str
    severity: QualitySeverity
    message: str
    actual_value: object = None
    expected_value: object = None


class SubtitleQualityAnalyzer:
    PROFILE = ValidationProfile(
        min_duration_ms=800,
        max_duration_ms=7000,
        max_cps=20.0,
        max_chars_per_line=42,
        max_lines=2,
        small_gap_ms=100,
        overlap_severity=Severity.ERROR,
        report_overlap_on_both_segments=False,
        count_newlines_in_cps=False,
    )

    _RULE_IDS = {
        "HIGH_CPS": "reading_speed",
        "TOO_SHORT": "duration_too_short",
        "TOO_LONG": "duration_too_long",
        "LINE_TOO_LONG": "line_too_long",
        "TOO_MANY_LINES": "too_many_lines",
        "OVERLAP": "subtitle_overlap",
        "SMALL_GAP": "gap_too_small",
    }

    @classmethod
    def analyze(cls, subtitles) -> list[QualityIssue]:
        snapshot = copy.deepcopy(list(subtitles or []))
        indexed = SubtitleValidator.validate_all(snapshot, profile=cls.PROFILE)
        issues = []
        for index in range(len(snapshot)):
            for issue in indexed.get(index, []):
                rule_id = cls._RULE_IDS.get(issue.code)
                if rule_id is None:
                    continue
                issues.append(
                    QualityIssue(
                        subtitle_index=index,
                        rule_id=rule_id,
                        severity=cls._severity(issue.severity),
                        message=issue.message,
                    )
                )
        return issues

    @staticmethod
    def _severity(severity: Severity) -> QualitySeverity:
        return QualitySeverity[severity.name]
