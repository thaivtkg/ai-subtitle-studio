import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode


@dataclass(frozen=True)
class ProbeResult:
    has_video: bool
    video_codec: str | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    container: str | None = None
    extension: str = ".mp4"


class MediaProbe:
    def probe(self, file_path: str | Path) -> ProbeResult:
        path = Path(file_path)
        if not path.exists():
            raise MediaImportError(MediaImportErrorCode.MEDIA_NOT_FOUND, "Media file does not exist")
        if path.stat().st_size == 0:
            raise MediaImportError(MediaImportErrorCode.INVALID_MEDIA, "Media file is empty (size 0)")
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "stream=codec_type,codec_name,width,height:format=duration,format_name",
                    "-of", "json", str(path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise MediaImportError(
                MediaImportErrorCode.UNKNOWN,
                "ffprobe executable not found in system PATH",
                details={"exception_type": "FileNotFoundError"},
            ) from exc
        except Exception as exc:
            raise MediaImportError(
                MediaImportErrorCode.UNKNOWN,
                "Failed to execute media probe",
                details={"exception_type": type(exc).__name__},
            ) from exc

        if result.returncode != 0:
            raise MediaImportError(
                MediaImportErrorCode.INVALID_MEDIA,
                "Invalid media file or corrupt container",
                details={"returncode": result.returncode},
            )
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise MediaImportError(
                MediaImportErrorCode.INVALID_MEDIA,
                "Failed to parse media probe output",
                details={"exception_type": "JSONDecodeError"},
            ) from exc

        streams = data.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        if not video:
            raise MediaImportError(
                MediaImportErrorCode.NO_VIDEO_STREAM,
                "Media file contains no video stream",
            )
        duration_value = data.get("format", {}).get("duration")
        try:
            duration = float(duration_value) if duration_value is not None else 0.0
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            raise MediaImportError(MediaImportErrorCode.INVALID_MEDIA, "Media duration is zero or invalid")
        format_name = data.get("format", {}).get("format_name", "")
        format_name_lower = str(format_name).lower()
        if "mp4" in format_name_lower or "mov" in format_name_lower:
            extension = ".mp4"
        elif "matroska" in format_name_lower or "webm" in format_name_lower:
            extension = ".mkv"
        elif "avi" in format_name_lower:
            extension = ".avi"
        elif "mpegts" in format_name_lower:
            extension = ".ts"
        elif "mpeg" in format_name_lower:
            extension = ".mpg"
        else:
            extension = ".mp4"
        return ProbeResult(
            has_video=True,
            video_codec=video.get("codec_name"),
            duration=duration,
            width=video.get("width"),
            height=video.get("height"),
            container=format_name or None,
            extension=extension,
        )
