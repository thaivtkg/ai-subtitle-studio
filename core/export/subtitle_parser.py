import re
import uuid


def _to_ms(value):
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    h, m, s, ms = map(int, match.groups())
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse_srt_content(content: str) -> list[dict]:
    segments = []
    for block in re.split(r"\n{2,}", content.replace("\r\n", "\n").strip()):
        lines = block.splitlines()
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        start, end = (part.strip() for part in lines[1].split("-->", 1))
        segments.append({
            "id": uuid.uuid4().hex,
            "stt": str(len(segments) + 1),
            "start": _to_ms(start), "end": _to_ms(end),
            "text": "\n".join(lines[2:]), "status": "draft",
            "metadata": {"type": "normal"},
        })
    return segments
