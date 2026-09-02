import os
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportProgress, MediaImportResult, MediaImportStage
from core.media_import.media_probe import MediaProbe
from core.media_import.network_safety import NetworkSafetyPolicy
from core.media_import.url_classifier import MediaURLType, URLClassifier
from core.runtime.runtime_paths import RuntimePaths

if TYPE_CHECKING:
    from core.media_import.adapters.direct_http_adapter import DirectHTTPAdapter
    from core.media_import.adapters.yt_dlp_adapter import YtDlpAdapter


class MediaImportService:
    def __init__(self, safety_policy=None, url_classifier=None, direct_adapter=None,
                 ytdlp_adapter=None, media_probe=None, storage_root=None):
        self.safety_policy = safety_policy or NetworkSafetyPolicy()
        self.url_classifier = url_classifier or URLClassifier()
        if direct_adapter is None:
            from core.media_import.adapters.direct_http_adapter import DirectHTTPAdapter
            direct_adapter = DirectHTTPAdapter(self.safety_policy)
        if ytdlp_adapter is None:
            from core.media_import.adapters.yt_dlp_adapter import YtDlpAdapter
            ytdlp_adapter = YtDlpAdapter()
        self.direct_adapter = direct_adapter
        self.ytdlp_adapter = ytdlp_adapter
        self.media_probe = media_probe or MediaProbe()
        self.storage_root = Path(storage_root) if storage_root is not None else RuntimePaths.get_media_imports_dir()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _check_cancel(cancel_flag):
        if cancel_flag and cancel_flag.is_set():
            raise MediaImportError(MediaImportErrorCode.DOWNLOAD_CANCELLED, "Download cancelled by user")

    def import_from_url(self, url: str, progress_callback=None, cancel_flag=None) -> MediaImportResult:
        self._check_cancel(cancel_flag)
        if progress_callback:
            progress_callback(MediaImportProgress(stage=MediaImportStage.RESOLVING))
        url_type = self.url_classifier.classify(url)
        target = self.safety_policy.validate_url(url)
        self._check_cancel(cancel_flag)

        import_dir = self.storage_root / uuid.uuid4().hex[:12]
        staging_dir = import_dir / ".staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        try:
            if progress_callback:
                progress_callback(MediaImportProgress(stage=MediaImportStage.DOWNLOADING))
            name = Path(urlsplit(target.original_url).path).name or "download"
            staging_target = staging_dir / name
            adapter = self.direct_adapter if url_type == MediaURLType.DIRECT_MEDIA else self.ytdlp_adapter
            download = adapter.download(target, staging_target, progress_callback=progress_callback, cancel_flag=cancel_flag)
            self._check_cancel(cancel_flag)
            downloaded = Path(download.local_path).resolve()
            if not downloaded.exists():
                raise MediaImportError(MediaImportErrorCode.MEDIA_NOT_FOUND, "Downloaded media file does not exist in staging")
            if staging_dir.resolve() not in downloaded.parents:
                raise MediaImportError(MediaImportErrorCode.FINALIZE_FAILED, "Downloaded media escaped staging directory")
            if progress_callback:
                progress_callback(MediaImportProgress(stage=MediaImportStage.VALIDATING))
            probe = self.media_probe.probe(downloaded)
            self._check_cancel(cancel_flag)
            if progress_callback:
                progress_callback(MediaImportProgress(stage=MediaImportStage.FINALIZING))
            ext = downloaded.suffix if downloaded.suffix and downloaded.suffix != ".tmp" else Path(download.filename).suffix
            final_path = import_dir / f"source{ext or '.mp4'}"
            os.replace(downloaded, final_path)
            shutil.rmtree(staging_dir, ignore_errors=True)
            metadata = dict(download.metadata)
            metadata.update(duration=probe.duration, video_codec=probe.video_codec, width=probe.width, height=probe.height)
            return MediaImportResult(str(final_path), target.original_url, final_path.name,
                                     final_path.stat().st_size, download.media_type, metadata)
        except Exception as exc:
            shutil.rmtree(import_dir, ignore_errors=True)
            if isinstance(exc, MediaImportError):
                raise
            raise MediaImportError(MediaImportErrorCode.UNKNOWN, "Unexpected error during media import pipeline",
                                   details={"exception_type": type(exc).__name__}) from exc
