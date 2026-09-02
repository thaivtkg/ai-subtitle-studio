import dataclasses
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import (
    MediaImportProgress,
    MediaImportResult,
    MediaImportStage,
)
from core.runtime.runtime_paths import RuntimePaths


class TestMediaImportContracts(unittest.TestCase):
    def test_media_import_stage_contract(self):
        self.assertEqual(
            {stage.value for stage in MediaImportStage},
            {"RESOLVING", "DOWNLOADING", "VALIDATING", "FINALIZING"},
        )

    def test_progress_supports_indeterminate_download(self):
        progress = MediaImportProgress(stage=MediaImportStage.DOWNLOADING)
        self.assertEqual(progress.downloaded_bytes, 0)
        self.assertIsNone(progress.total_bytes)
        self.assertIsNone(progress.percent)
        self.assertIsNone(progress.speed_bytes_per_sec)
        self.assertIsNone(progress.eta_seconds)

    def test_error_taxonomy_contains_required_codes(self):
        required_codes = {
            "INVALID_URL", "UNSAFE_URL", "UNSUPPORTED_URL", "NETWORK_ERROR",
            "TIMEOUT", "HTTP_ERROR", "AUTH_REQUIRED", "DRM_OR_PROTECTED",
            "MEDIA_NOT_FOUND", "INVALID_MEDIA", "NO_VIDEO_STREAM", "DISK_FULL",
            "PERMISSION_DENIED", "DOWNLOAD_CANCELLED", "FINALIZE_FAILED", "UNKNOWN",
        }
        enum_codes = {item.value for item in MediaImportErrorCode}
        self.assertTrue(required_codes.issubset(enum_codes))
        err = MediaImportError(
            MediaImportErrorCode.UNSAFE_URL,
            "Access to private IP blocked",
            details={"ip": "127.0.0.1"},
        )
        self.assertIsInstance(err, Exception)
        self.assertEqual(err.code, MediaImportErrorCode.UNSAFE_URL)
        self.assertEqual(str(err), "Access to private IP blocked")
        self.assertEqual(err.details, {"ip": "127.0.0.1"})

    def test_models_are_frozen(self):
        progress = MediaImportProgress(MediaImportStage.DOWNLOADING, 1024, 2048, 50.0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            progress.downloaded_bytes = 2048
        result = MediaImportResult(
            "/path/to/media.mp4", "https://example.com/video.mp4", "media.mp4",
            2048, "video/mp4", {"duration": 12.5},
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.size_bytes = 4096

    def test_media_imports_dir_is_app_owned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.dict(os.environ, {"LOCALAPPDATA": str(temp_root)}):
                import_dir = RuntimePaths.get_media_imports_dir()
                self.assertEqual(import_dir, RuntimePaths.get_user_data_dir() / "media_imports")
                self.assertTrue(str(import_dir).startswith(str(temp_root)))

    def test_ensure_user_data_dirs_creates_media_imports_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOCALAPPDATA": str(Path(temp_dir))}):
                import_dir = RuntimePaths.get_media_imports_dir()
                self.assertFalse(import_dir.exists())
                RuntimePaths.ensure_user_data_dirs()
                self.assertTrue(import_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
