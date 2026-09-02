import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportProgress, MediaImportResult, MediaImportStage
from core.media_import.url_classifier import MediaURLType

try:
    from core.media_import.media_import_service import MediaImportService
    from core.media_import.media_probe import MediaProbe, ProbeResult
except (ModuleNotFoundError, ImportError):
    MediaImportService = None
    MediaProbe = None
    ProbeResult = None


class TestMediaProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MediaProbe is None:
            raise unittest.SkipTest("SUT MediaProbe not implemented")

    def setUp(self):
        self.probe = MediaProbe()
        self.temp_file = Path(tempfile.mktemp(suffix=".mp4"))
        self.temp_file.write_bytes(b"dummy")

    def tearDown(self):
        self.temp_file.unlink(missing_ok=True)

    @patch("subprocess.run")
    def test_probe_accepts_valid_video_stream(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}, {"codec_type": "audio", "codec_name": "aac"}], "format": {"duration": "120.5"}}',
        )
        result = self.probe.probe(self.temp_file)
        self.assertIsInstance(result, ProbeResult)
        self.assertTrue(result.has_video)
        self.assertEqual(result.video_codec, "h264")
        self.assertEqual(result.duration, 120.5)

    @patch("subprocess.run")
    def test_probe_rejects_audio_only_stream(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"codec_type": "audio", "codec_name": "aac"}], "format": {"duration": "60.0"}}',
        )
        with self.assertRaises(MediaImportError) as ctx:
            self.probe.probe(self.temp_file)
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NO_VIDEO_STREAM)

    @patch("subprocess.run")
    def test_probe_rejects_corrupted_or_non_media(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stderr="Invalid data found when processing input"
        )
        with self.assertRaises(MediaImportError) as ctx:
            self.probe.probe(self.temp_file)
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.INVALID_MEDIA)

    @patch("subprocess.run")
    def test_probe_maps_format_to_safe_extension(self, mock_run):
        cases = [
            ("mov,mp4,m4a,3gp,3g2,mj2", ".mp4"),
            ("matroska,webm", ".mkv"),
            ("avi", ".avi"),
            ("mpegts", ".ts"),
            ("mpeg", ".mpg"),
            ("unknown_format", ".mp4"),
        ]
        for fmt, expected_ext in cases:
            with self.subTest(fmt=fmt):
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=(
                        '{"streams": [{"codec_type": "video", "codec_name": "h264"}], '
                        f'"format": {{"duration": "10.0", "format_name": "{fmt}"}}}}'
                    ),
                )
                result = self.probe.probe(self.temp_file)
                self.assertEqual(result.container, fmt)
                self.assertEqual(result.extension, expected_ext)

    @patch("subprocess.run")
    def test_probe_enforces_shell_false(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                '{"streams": [{"codec_type": "video", "codec_name": "h264"}], '
                '"format": {"duration": "10.0", "format_name": "mp4"}}'
            ),
        )
        self.probe.probe(self.temp_file)
        self.assertFalse(mock_run.call_args.kwargs["shell"])


class TestMediaImportService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if MediaImportService is None:
            raise unittest.SkipTest("SUT MediaImportService not implemented")

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.media_imports_dir = Path(self.temp_dir) / "media_imports"
        self.media_imports_dir.mkdir(parents=True, exist_ok=True)
        self.safety_policy = MagicMock()
        self.url_classifier = MagicMock()
        self.direct_adapter = MagicMock()
        self.ytdlp_adapter = MagicMock()
        self.media_probe = MagicMock()
        self.service = MediaImportService(
            safety_policy=self.safety_policy,
            url_classifier=self.url_classifier,
            direct_adapter=self.direct_adapter,
            ytdlp_adapter=self.ytdlp_adapter,
            media_probe=self.media_probe,
            storage_root=self.media_imports_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pipeline_emits_stages_in_order_and_atomic_finalizes(self):
        url = "https://example.com/video.mp4"
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        target = MagicMock(original_url=url, hostname="example.com", resolved_ips=("93.184.216.34",))
        self.safety_policy.validate_url.return_value = target

        def fake_download(_target, dest_path, progress_callback=None, cancel_flag=None):
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"dummy_video_payload")
            return MediaImportResult(str(dest), url, "video.mp4", 19, "video/mp4", {})

        self.direct_adapter.download.side_effect = fake_download
        self.media_probe.probe.return_value = ProbeResult(True, "h264", 10.0, 1920, 1080)
        stages_emitted = []

        def progress_cb(progress):
            if not stages_emitted or stages_emitted[-1] != progress.stage:
                stages_emitted.append(progress.stage)

        result = self.service.import_from_url(url, progress_callback=progress_cb)
        self.assertEqual(stages_emitted, [MediaImportStage.RESOLVING, MediaImportStage.DOWNLOADING, MediaImportStage.VALIDATING, MediaImportStage.FINALIZING])
        final_file = Path(result.local_path)
        self.assertTrue(final_file.exists())
        self.assertEqual(final_file.name, "source.mp4")
        self.assertNotIn(".staging", final_file.parts)
        self.assertFalse((final_file.parent / ".staging").exists())

    def test_pipeline_cleans_up_staging_on_probe_failure(self):
        url = "https://example.com/audio.mp3"
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        self.safety_policy.validate_url.return_value = MagicMock(original_url=url, resolved_ips=("93.184.216.34",))

        def fake_download(_target, dest_path, progress_callback=None, cancel_flag=None):
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"dummy_audio_payload")
            return MediaImportResult(str(dest), url, "audio.mp3", 19, "audio/mp3", {})

        self.direct_adapter.download.side_effect = fake_download
        self.media_probe.probe.side_effect = MediaImportError(MediaImportErrorCode.NO_VIDEO_STREAM, "Audio-only streams not supported")
        with self.assertRaises(MediaImportError) as ctx:
            self.service.import_from_url(url)
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NO_VIDEO_STREAM)
        self.assertEqual(len(list(self.media_imports_dir.iterdir())), 0)

    def test_pipeline_routes_webpage_to_ytdlp_adapter(self):
        url = "https://youtube.com/watch?v=123"
        self.url_classifier.classify.return_value = MediaURLType.PAGE_OR_EXTRACTOR
        self.safety_policy.validate_url.return_value = MagicMock(original_url=url, resolved_ips=("93.184.216.34",))

        def fake_download(_target, dest_path, progress_callback=None, cancel_flag=None):
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"dummy_ytdlp_payload")
            return MediaImportResult(str(dest), url, "watch.mp4", 19, "mp4", {})

        self.ytdlp_adapter.download.side_effect = fake_download
        self.media_probe.probe.return_value = ProbeResult(True, "vp9", 50.0, 1280, 720)
        self.service.import_from_url(url)
        self.ytdlp_adapter.download.assert_called_once()
        self.direct_adapter.download.assert_not_called()

    def _mock_success_download(self, adapter):
        def download(_target, dest_path, _callback, _cancel_flag):
            dest = Path(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"data")
            return MediaImportResult(str(dest), "url", "test.mp4", 4, "video/mp4", {})
        adapter.download.side_effect = download

    def test_direct_invalid_media_falls_back_to_ytdlp(self):
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        self.safety_policy.validate_url.return_value = MagicMock(
            original_url="https://url", resolved_ips=("1.1.1.1",)
        )
        self._mock_success_download(self.direct_adapter)
        self._mock_success_download(self.ytdlp_adapter)
        self.media_probe.probe.side_effect = [
            MediaImportError(MediaImportErrorCode.INVALID_MEDIA, "HTML payload"),
            ProbeResult(True, "h264", 10.0, 1920, 1080),
        ]
        self.service.import_from_url("https://url")
        self.direct_adapter.download.assert_called_once()
        self.ytdlp_adapter.download.assert_called_once()

    def test_direct_network_error_does_not_fall_back(self):
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        self.safety_policy.validate_url.return_value = MagicMock(
            original_url="https://url", resolved_ips=("1.1.1.1",)
        )
        self.direct_adapter.download.side_effect = MediaImportError(
            MediaImportErrorCode.NETWORK_ERROR, ""
        )
        with self.assertRaises(MediaImportError) as ctx:
            self.service.import_from_url("https://url")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NETWORK_ERROR)
        self.ytdlp_adapter.download.assert_not_called()

    def test_webpage_unsupported_falls_back_to_direct(self):
        self.url_classifier.classify.return_value = MediaURLType.PAGE_OR_EXTRACTOR
        self.safety_policy.validate_url.return_value = MagicMock(
            original_url="https://url", resolved_ips=("1.1.1.1",)
        )
        self.ytdlp_adapter.download.side_effect = MediaImportError(
            MediaImportErrorCode.UNSUPPORTED_URL, ""
        )
        self._mock_success_download(self.direct_adapter)
        self.media_probe.probe.return_value = ProbeResult(True, "h264", 10.0, 1920, 1080)
        self.service.import_from_url("https://url")
        self.ytdlp_adapter.download.assert_called_once()
        self.direct_adapter.download.assert_called_once()

    def test_direct_audio_only_does_not_fall_back(self):
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        self.safety_policy.validate_url.return_value = MagicMock(
            original_url="https://url", resolved_ips=("1.1.1.1",)
        )
        self._mock_success_download(self.direct_adapter)
        self.media_probe.probe.side_effect = MediaImportError(
            MediaImportErrorCode.NO_VIDEO_STREAM, ""
        )
        with self.assertRaises(MediaImportError) as ctx:
            self.service.import_from_url("https://url")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NO_VIDEO_STREAM)
        self.ytdlp_adapter.download.assert_not_called()

    @patch("os.replace")
    def test_finalize_failure_is_mapped_and_cleaned(self, mock_replace):
        self.url_classifier.classify.return_value = MediaURLType.DIRECT_MEDIA
        self.safety_policy.validate_url.return_value = MagicMock(
            original_url="https://url", resolved_ips=("1.1.1.1",)
        )
        self._mock_success_download(self.direct_adapter)
        self.media_probe.probe.return_value = ProbeResult(True, "h264", 10.0, 1920, 1080)
        mock_replace.side_effect = OSError("Access Denied")
        with self.assertRaises(MediaImportError) as ctx:
            self.service.import_from_url("https://url")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.FINALIZE_FAILED)
        self.assertEqual(len(list(self.media_imports_dir.iterdir())), 0)

    def test_webpage_auth_drm_network_no_fallback(self):
        self.url_classifier.classify.return_value = MediaURLType.PAGE_OR_EXTRACTOR
        target = MagicMock(original_url="https://url", resolved_ips=("1.1.1.1",))
        self.safety_policy.validate_url.return_value = target
        for error_code in (
            MediaImportErrorCode.AUTH_REQUIRED,
            MediaImportErrorCode.DRM_OR_PROTECTED,
            MediaImportErrorCode.TIMEOUT,
            MediaImportErrorCode.NETWORK_ERROR,
        ):
            with self.subTest(error_code=error_code):
                self.ytdlp_adapter.reset_mock()
                self.direct_adapter.reset_mock()
                self.ytdlp_adapter.download.side_effect = MediaImportError(error_code, "")
                with self.assertRaises(MediaImportError) as ctx:
                    self.service.import_from_url("https://url")
                self.assertEqual(ctx.exception.code, error_code)
                self.ytdlp_adapter.download.assert_called_once()
                self.direct_adapter.download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
