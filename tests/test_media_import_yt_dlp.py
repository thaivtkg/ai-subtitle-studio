import sys
import unittest
from types import ModuleType
from unittest.mock import MagicMock, patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportProgress, MediaImportStage

if "yt_dlp" not in sys.modules:
    fake_yt_dlp = ModuleType("yt_dlp")
    fake_utils = ModuleType("yt_dlp.utils")

    class FakeDownloadError(Exception):
        pass

    fake_utils.DownloadError = FakeDownloadError
    fake_yt_dlp.utils = fake_utils
    fake_yt_dlp.YoutubeDL = MagicMock()
    sys.modules["yt_dlp"] = fake_yt_dlp
    sys.modules["yt_dlp.utils"] = fake_utils

import yt_dlp
from core.media_import.adapters.yt_dlp_adapter import YtDlpAdapter


class TestYtDlpAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = YtDlpAdapter()
        self.mock_target = MagicMock(
            original_url="https://youtube.com/watch?v=123",
            resolved_ips=("93.184.216.34",),
            hostname="youtube.com",
        )

    @patch("core.media_import.adapters.yt_dlp_adapter.yt_dlp.YoutubeDL")
    def test_maps_authentication_errors(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(
            "Sign in to confirm you’re not a bot"
        )
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, "/tmp/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.AUTH_REQUIRED)

    @patch("core.media_import.adapters.yt_dlp_adapter.yt_dlp.YoutubeDL")
    def test_maps_drm_and_unsupported_errors(self, mock_ydl_cls):
        error_cases = [
            ("This video is DRM protected", MediaImportErrorCode.DRM_OR_PROTECTED),
            ("Unsupported URL: https://example.com", MediaImportErrorCode.UNSUPPORTED_URL),
            ("No video formats found", MediaImportErrorCode.NO_VIDEO_STREAM),
            ("urlopen error timed out", MediaImportErrorCode.TIMEOUT),
            ("Connection refused", MediaImportErrorCode.NETWORK_ERROR),
        ]
        for error_msg, expected_code in error_cases:
            with self.subTest(error_msg=error_msg):
                mock_ydl = MagicMock()
                mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(error_msg)
                mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
                with self.assertRaises(MediaImportError) as ctx:
                    self.adapter.download(self.mock_target, "/tmp/out.mp4")
                self.assertEqual(ctx.exception.code, expected_code)

    @patch("core.media_import.adapters.yt_dlp_adapter.yt_dlp.YoutubeDL")
    def test_emits_standardized_progress(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        progress_calls = []

        def trigger_progress(*_args, **_kwargs):
            hooks = mock_ydl_cls.call_args.kwargs.get("params", {}).get("progress_hooks", [])
            for hook in hooks:
                hook({"status": "downloading", "downloaded_bytes": 500,
                      "total_bytes": 1000, "speed": 100, "eta": 5})
            return {"ext": "mp4", "title": "test", "requested_downloads": [{"filepath": "/tmp/out.mp4"}]}

        mock_ydl.extract_info.side_effect = trigger_progress
        self.adapter.download(self.mock_target, "/tmp/out.mp4", progress_callback=progress_calls.append)
        progress = progress_calls[0]
        self.assertEqual(progress.stage, MediaImportStage.DOWNLOADING)
        self.assertEqual(progress.downloaded_bytes, 500)
        self.assertEqual(progress.total_bytes, 1000)
        self.assertEqual(progress.speed_bytes_per_sec, 100)
        self.assertEqual(progress.eta_seconds, 5)
        self.assertEqual(progress.percent, 50.0)

    @patch("core.media_import.adapters.yt_dlp_adapter.yt_dlp.YoutubeDL")
    def test_respects_cancellation_flag(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        cancel_flag = MagicMock()
        cancel_flag.is_set.return_value = True

        def trigger_progress(*_args, **_kwargs):
            for hook in mock_ydl_cls.call_args.kwargs.get("params", {}).get("progress_hooks", []):
                hook({"status": "downloading"})

        mock_ydl.extract_info.side_effect = trigger_progress
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, "/tmp/out.mp4", cancel_flag=cancel_flag)
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.DOWNLOAD_CANCELLED)

    @patch("yt_dlp.YoutubeDL")
    def test_enforces_safe_ydl_options(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {"filepath": "/tmp/out.mp4"}
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 500
            self.adapter.download(self.mock_target, "/tmp/out.mp4")
        opts = mock_ydl_cls.call_args.kwargs["params"]
        self.assertEqual(opts["format"], "bestvideo*+bestaudio/best")
        self.assertTrue(opts["noplaylist"])
        self.assertNotIn("cookiesfrombrowser", opts)
        self.assertNotIn("username", opts)
        self.assertNotIn("password", opts)
        self.assertNotIn("external_downloader", opts)

    @patch("yt_dlp.YoutubeDL")
    def test_rejects_unconfined_output_path(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {"filepath": "/etc/passwd"}
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, "/tmp/staging/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.FINALIZE_FAILED)
        self.assertIn("unsafe output path", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
