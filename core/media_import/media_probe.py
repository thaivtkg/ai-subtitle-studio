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


class MediaProbe:
    def probe(self, file_path: str | Path) -> ProbeResult:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
                    "-of", "json", str(Path(file_path)),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
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
        return ProbeResult(
            has_video=True,
            video_codec=video.get("codec_name"),
            duration=float(duration_value) if duration_value is not None else None,
            width=video.get("width"),
            height=video.get("height"),
        )
