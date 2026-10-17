"""Locale-tolerant parsing for subtitle range time inputs.

The UI chooses the unit explicitly (seconds or minutes); values are converted to
integer milliseconds immediately so the rest of the application stays unit-safe.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re


_UNIT_TO_MS = {
    "seconds": Decimal("1000"),
    "minutes": Decimal("60000"),
}
_NUMBER_RE = re.compile(r"^(?:\d+(?:[.,]\d+)?|[.,]\d+)$")


class RangeInputError(ValueError):
    """Raised when a range boundary is not a valid non-negative decimal."""


def parse_range_value_ms(text: str, unit: str) -> int:
    """Parse a numeric string into milliseconds using the selected unit.

    Supports either comma or dot decimal separator, e.g. ``60,5`` seconds or
    ``1.5`` minutes. Unit suffixes are intentionally not accepted: the combo box
    is the single source of truth for units.
    """
    if unit not in _UNIT_TO_MS:
        raise RangeInputError("Hãy chọn đơn vị Giây hoặc Phút.")

    raw = str(text or "").strip()
    if not raw:
        raise RangeInputError("Vui lòng nhập giá trị thời gian.")
    if len(raw) > 32:
        raise RangeInputError("Giá trị quá dài. Hãy nhập một số thời gian ngắn gọn.")
    if not _NUMBER_RE.fullmatch(raw):
        unit_hint = "giây" if unit == "seconds" else "phút"
        raise RangeInputError(
            f"Chỉ nhập số không âm theo đơn vị {unit_hint}; dùng dấu phẩy hoặc dấu chấm cho số lẻ."
        )

    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise RangeInputError("Giá trị thời gian không hợp lệ.") from exc

    if not value.is_finite() or value < 0:
        raise RangeInputError("Thời gian phải là số không âm.")

    milliseconds = value * _UNIT_TO_MS[unit]
    return int(milliseconds.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_range_value_ms(value_ms: int, unit: str) -> str:
    """Format milliseconds as a compact decimal for the selected unit."""
    if unit not in _UNIT_TO_MS:
        raise RangeInputError("Hãy chọn đơn vị Giây hoặc Phút.")
    value = Decimal(int(value_ms)) / _UNIT_TO_MS[unit]
    # Show precision sufficient for millisecond-resolution values without
    # producing long repeating decimals when converting between units.
    quantum = Decimal("0.001") if unit == "seconds" else Decimal("0.000001")
    value = value.quantize(quantum, rounding=ROUND_HALF_UP)
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"
