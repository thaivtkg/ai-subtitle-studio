from core.export.subtitle_parser import parse_srt_content


class SrtParser:
    """Cầu nối đọc tệp SRT an toàn, hỗ trợ fallback mã hóa ký tự."""

    @staticmethod
    def parse(path: str) -> list[dict]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return parse_srt_content(f.read())
