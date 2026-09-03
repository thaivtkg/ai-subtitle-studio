from pathlib import Path
import socket

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import (
    MediaImportProgress,
    MediaImportResult,
    MediaImportStage,
)
from core.media_import.network_safety import NetworkSafetyPolicy, SafeResolvedTarget, SafeSocketContext


class YtDlpAdapter:
    def __init__(self, safety_policy: NetworkSafetyPolicy | None = None):
        self.safety_policy = safety_policy or NetworkSafetyPolicy()

    def _map_download_error(self, exc: Exception) -> MediaImportError:
        message = str(exc).lower()
        if (
            "blocked connection to unsafe ip" in message
            or "unsafe or private ip" in message
            or "unsafe_url" in message
        ):
            code = MediaImportErrorCode.UNSAFE_URL
            text = "Blocked connection to unsafe or private IP"
        elif "sign in" in message or "authentication" in message or "bot" in message:
            code = MediaImportErrorCode.AUTH_REQUIRED
            text = "Authentication required"
        elif "drm" in message or "protected" in message:
            code = MediaImportErrorCode.DRM_OR_PROTECTED
            text = "Media is DRM protected"
        elif "unsupported url" in message:
            code = MediaImportErrorCode.UNSUPPORTED_URL
            text = "Unsupported media URL"
        elif "no video formats" in message or "no video" in message:
            code = MediaImportErrorCode.NO_VIDEO_STREAM
            text = "No extractable stream found"
        elif "time out" in message or "timed out" in message:
            code = MediaImportErrorCode.TIMEOUT
            text = "Connection timed out"
        elif "connection refused" in message or "network is unreachable" in message:
            code = MediaImportErrorCode.NETWORK_ERROR
            text = "Network error"
        else:
            code = MediaImportErrorCode.UNKNOWN
            text = "Failed to download media via extractor"
        return MediaImportError(code, text, details={"exception_type": type(exc).__name__})

    def download(
        self,
        target: SafeResolvedTarget,
        dest_path: str | Path,
        progress_callback=None,
        cancel_flag=None,
    ) -> MediaImportResult:
        if yt_dlp is None:
            raise MediaImportError(
                MediaImportErrorCode.UNKNOWN,
                "yt-dlp is not installed in the current environment",
            )
        dest_path = Path(dest_path).resolve()
        outtmpl = str(dest_path.with_name(dest_path.name + ".%(ext)s"))

        def hook(data):
            if cancel_flag and cancel_flag.is_set():
                raise ValueError("DOWNLOAD_CANCELLED_BY_USER")
            if data.get("status") != "downloading" or not progress_callback:
                return
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            speed = data.get("speed")
            eta = data.get("eta")
            progress_callback(
                MediaImportProgress(
                    stage=MediaImportStage.DOWNLOADING,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    speed_bytes_per_sec=float(speed) if speed else None,
                    eta_seconds=float(eta) if eta else None,
                    percent=(downloaded / total * 100) if total else None,
                )
            )

        options = {
            "outtmpl": outtmpl,
            "format": "bestvideo*+bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "cookiefile": None,
            "updatetime": False,
            "hls_prefer_native": True,
            "proxy": "",
        }
        try:
            with SafeSocketContext(self.safety_policy):
                with yt_dlp.YoutubeDL(params=options) as ydl:
                    info = ydl.extract_info(target.original_url, download=True)
                    final_path = info.get("filepath")
                    if not final_path:
                        requested = info.get("requested_downloads", [{}])
                        final_path = requested[0].get("filepath", str(dest_path))
                    path = Path(final_path).resolve()
                    root = dest_path.parent.resolve()
                    if path != dest_path and root not in path.parents:
                        raise MediaImportError(
                            MediaImportErrorCode.FINALIZE_FAILED,
                            "Extractor returned an unsafe output path",
                        )
                    return MediaImportResult(
                        local_path=str(path),
                        original_url=target.original_url,
                        filename=path.name,
                        size_bytes=path.stat().st_size if path.exists() else 0,
                        media_type=info.get("ext", "unknown"),
                        metadata={"extractor": info.get("extractor")},
                    )
        except ValueError as exc:
            if "DOWNLOAD_CANCELLED_BY_USER" in str(exc):
                raise MediaImportError(
                    MediaImportErrorCode.DOWNLOAD_CANCELLED,
                    "Download cancelled",
                ) from exc
            raise MediaImportError(
                MediaImportErrorCode.UNKNOWN,
                "Unexpected error during extraction",
                details={"exception_type": type(exc).__name__},
            ) from exc
        except yt_dlp.utils.DownloadError as exc:
            raise self._map_download_error(exc) from exc
        except MediaImportError:
            raise
        except socket.gaierror as exc:
            if "blocked connection to unsafe ip" in str(exc).lower():
                raise MediaImportError(
                    MediaImportErrorCode.UNSAFE_URL,
                    "Blocked connection to unsafe or private IP",
                    details={"exception_type": type(exc).__name__},
                ) from exc
            raise MediaImportError(
                MediaImportErrorCode.NETWORK_ERROR,
                "Network error during extraction",
                details={"exception_type": type(exc).__name__},
            ) from exc
        except Exception as exc:
            raise MediaImportError(
                MediaImportErrorCode.UNKNOWN,
                "Unexpected error during extraction",
                details={"exception_type": type(exc).__name__},
            ) from exc
