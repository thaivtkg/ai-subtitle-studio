def format_srt_timestamp(value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        hours, remainder = divmod(value, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    return str(value)


def generate_srt_content(segments: list[dict]) -> str:
    blocks = []
    for segment in segments:
        text = segment.get("text", "")
        if text == "[ Chưa có nội dung ]":
            text = ""
        blocks.append(
            f"{segment.get('stt', '')}\n"
            f"{format_srt_timestamp(segment.get('start', 0))} --> "
            f"{format_srt_timestamp(segment.get('end', 0))}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")
