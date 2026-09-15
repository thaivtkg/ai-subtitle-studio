import os
import tempfile
from dataclasses import dataclass

from core.subtitle_placement import normalized_to_pixel_anchor


def escape_ass_text(text: str) -> str:
    """Escape subtitle text without re-processing escape sequences we create."""
    escaped = []
    for char in str(text).replace("\r\n", "\n").replace("\r", "\n"):
        if char == "\n":
            escaped.append(r"\N")
        elif char == "\\":
            escaped.append(r"\\")
        elif char == "{":
            escaped.append(r"\{")
        elif char == "}":
            escaped.append(r"\}")
        else:
            escaped.append(char)
    return "".join(escaped)


def build_ass_dialogue(text: str, width: int, height: int, x: float, y: float) -> str:
    pixel_x, pixel_y = normalized_to_pixel_anchor(width, height, x, y)
    return f"{{\\an5\\pos({pixel_x},{pixel_y})}}{escape_ass_text(text)}"


@dataclass
class TemporaryAssFile:
    path: str
    _cleaned: bool = False

    def finish(self, outcome: str) -> None:
        if self._cleaned:
            return
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
        self._cleaned = True


def temporary_ass_file(text: str) -> TemporaryAssFile:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".ass",
        prefix="subtitle_",
        delete=False,
    )
    try:
        handle.write(str(text))
    finally:
        handle.close()
    return TemporaryAssFile(handle.name)
