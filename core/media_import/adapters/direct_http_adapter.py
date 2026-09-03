import errno
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import urllib3
import urllib3.exceptions

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import (
    MediaImportProgress,
    MediaImportResult,
    MediaImportStage,
)
from core.media_import.network_safety import NetworkSafetyPolicy, SafeResolvedTarget


class DirectHTTPAdapter:
    def __init__(self, safety_policy: NetworkSafetyPolicy, max_redirects: int = 5):
        self.safety_policy = safety_policy
        self.max_redirects = max_redirects

    def download(
        self,
        target: SafeResolvedTarget,
        dest_path: str | Path,
        progress_callback=None,
        cancel_flag=None,
    ) -> MediaImportResult:
        dest_path = Path(dest_path)
        current_target = target
        redirect_count = 0

        while redirect_count <= self.max_redirects:
            self._check_cancelled(cancel_flag)
            parsed = urlsplit(current_target.original_url)
            ip = current_target.resolved_ips[0]
            ip_netloc = f"[{ip}]" if ":" in ip else ip
            if current_target.port not in (80, 443):
                ip_netloc += f":{current_target.port}"
            request_url = urlunsplit(
                (current_target.scheme, ip_netloc, parsed.path, parsed.query, parsed.fragment)
            )
            headers = {
                "Host": current_target.hostname,
                "User-Agent": "AI-Subtitle-Studio/1.0",
            }
            pool_kwargs = {}
            if current_target.scheme == "https":
                pool_kwargs.update(
                    server_hostname=current_target.hostname,
                    assert_hostname=current_target.hostname,
                )
            http = urllib3.PoolManager(**pool_kwargs)
            try:
                response = http.request(
                    "GET",
                    request_url,
                    headers=headers,
                    preload_content=False,
                    retries=False,
                    redirect=False,
                    timeout=15.0,
                )
            except urllib3.exceptions.TimeoutError as exc:
                raise MediaImportError(
                    MediaImportErrorCode.TIMEOUT,
                    "Media connection timed out",
                    details={"exception_type": type(exc).__name__},
                ) from exc
            except Exception as exc:
                raise MediaImportError(
                    MediaImportErrorCode.NETWORK_ERROR,
                    "Unable to connect to media server",
                    details={"exception_type": type(exc).__name__},
                ) from exc

            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                response.release_conn()
                if not location:
                    raise MediaImportError(
                        MediaImportErrorCode.HTTP_ERROR,
                        "Redirect missing Location header",
                    )
                current_target = self.safety_policy.validate_url(
                    urljoin(current_target.original_url, location)
                )
                redirect_count += 1
                continue

            if response.status not in (200, 206):
                response.release_conn()
                raise MediaImportError(
                    MediaImportErrorCode.HTTP_ERROR,
                    f"HTTP Error {response.status}",
                )

            total_header = response.headers.get("Content-Length")
            total_bytes = (
                int(total_header) if total_header and total_header.isdigit() else None
            )
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            filename = Path(parsed.path).name or "downloaded_media"
            downloaded_bytes = 0
            start_time = time.monotonic()
            try:
                with open(dest_path, "wb") as output:
                    for chunk in response.stream(8192):
                        self._check_cancelled(cancel_flag)
                        output.write(chunk)
                        downloaded_bytes += len(chunk)
                        if progress_callback:
                            elapsed = time.monotonic() - start_time
                            speed = downloaded_bytes / elapsed if elapsed > 0 else 0.0
                            percent = (
                                downloaded_bytes / total_bytes * 100
                                if total_bytes
                                else None
                            )
                            eta = (
                                (total_bytes - downloaded_bytes) / speed
                                if total_bytes and speed > 0
                                else None
                            )
                            progress_callback(
                                MediaImportProgress(
                                    stage=MediaImportStage.DOWNLOADING,
                                    downloaded_bytes=downloaded_bytes,
                                    total_bytes=total_bytes,
                                    speed_bytes_per_sec=speed,
                                    eta_seconds=eta,
                                    percent=percent,
                                )
                            )
            except urllib3.exceptions.TimeoutError as exc:
                raise MediaImportError(
                    MediaImportErrorCode.TIMEOUT,
                    "Media download timed out",
                    details={"exception_type": type(exc).__name__},
                ) from exc
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    code = MediaImportErrorCode.DISK_FULL
                    message = "Not enough disk space to download media"
                elif exc.errno in {errno.EACCES, errno.EPERM}:
                    code = MediaImportErrorCode.PERMISSION_DENIED
                    message = "Unable to write downloaded media"
                else:
                    code = MediaImportErrorCode.UNKNOWN
                    message = "Unable to write downloaded media"
                raise MediaImportError(
                    code,
                    message,
                    details={"exception_type": "OSError"},
                ) from exc
            except Exception as exc:
                if isinstance(exc, MediaImportError):
                    raise
                raise MediaImportError(
                    MediaImportErrorCode.NETWORK_ERROR,
                    "Unable to download media stream",
                    details={"exception_type": type(exc).__name__},
                ) from exc
            finally:
                response.release_conn()
            return MediaImportResult(
                local_path=str(dest_path),
                original_url=current_target.original_url,
                filename=filename,
                size_bytes=downloaded_bytes,
                media_type=content_type,
                metadata={"redirect_count": redirect_count},
            )

        raise MediaImportError(MediaImportErrorCode.HTTP_ERROR, "Too many redirects")

    @staticmethod
    def _check_cancelled(cancel_flag) -> None:
        if cancel_flag and cancel_flag.is_set():
            raise MediaImportError(
                MediaImportErrorCode.DOWNLOAD_CANCELLED,
                "Download cancelled",
            )
