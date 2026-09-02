import unittest
import tempfile
import errno
from unittest.mock import MagicMock, patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportStage

try:
    import urllib3.exceptions
    from core.media_import.adapters.direct_http_adapter import DirectHTTPAdapter
    from core.media_import.network_safety import SafeResolvedTarget
except (ModuleNotFoundError, ImportError):
    DirectHTTPAdapter = None
    SafeResolvedTarget = None


class TestDirectHTTPAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DirectHTTPAdapter is None:
            raise unittest.SkipTest(
                "SUT module core.media_import.adapters.direct_http_adapter not implemented"
            )

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.safety_policy = MagicMock()
        self.adapter = DirectHTTPAdapter(self.safety_policy)
        self.mock_target = MagicMock(
            original_url="https://example.com/video.mp4",
            scheme="https",
            hostname="example.com",
            port=443,
            resolved_ips=("93.184.216.34",),
        )

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_connects_to_pinned_ip_with_correct_host_header(self, mock_request):
        mock_response = MagicMock(status=200, headers={"Content-Length": "1024"})
        mock_response.stream.return_value = [b"data"]
        mock_request.return_value = mock_response
        self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        args, kwargs = mock_request.call_args
        actual_url = args[1] if len(args) > 1 else kwargs.get("url")
        self.assertTrue(actual_url.startswith("https://93.184.216.34"))
        self.assertEqual(kwargs.get("headers", {}).get("Host"), "example.com")
        server_hostname = kwargs.get("server_hostname") or kwargs.get("assert_hostname")
        self.assertIn(server_hostname, [None, self.mock_target.hostname])

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_manual_redirect_chain_is_revalidated_by_safety_policy(self, mock_request):
        redirect_response = MagicMock(
            status=302, headers={"Location": "https://malicious.com/video.mp4"}
        )
        self.safety_policy.validate_url.side_effect = MediaImportError(
            MediaImportErrorCode.UNSAFE_URL, "Malicious redirect"
        )
        mock_request.return_value = redirect_response
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)
        self.safety_policy.validate_url.assert_called_once_with(
            "https://malicious.com/video.mp4"
        )

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_emits_indeterminate_progress_if_content_length_is_missing(self, mock_request):
        mock_response = MagicMock(status=200, headers={})
        mock_response.stream.return_value = [b"chunk1", b"chunk2"]
        mock_request.return_value = mock_response
        progress_calls = []
        self.adapter.download(
            self.mock_target, self.temp_dir.name + "/out.mp4", progress_callback=progress_calls.append
        )
        last_progress = progress_calls[-1]
        self.assertEqual(last_progress.stage, MediaImportStage.DOWNLOADING)
        self.assertIsNone(last_progress.total_bytes)
        self.assertIsNone(last_progress.percent)
        self.assertEqual(last_progress.downloaded_bytes, 12)

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_respects_cancellation_flag(self, mock_request):
        mock_response = MagicMock(status=200, headers={"Content-Length": "1024"})
        mock_response.stream.return_value = [b"chunk1", b"chunk2", b"chunk3"]
        mock_request.return_value = mock_response
        cancel_flag = MagicMock()
        cancel_flag.is_set.side_effect = [False, True, True]
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(
                self.mock_target, self.temp_dir.name + "/out.mp4", cancel_flag=cancel_flag
            )
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.DOWNLOAD_CANCELLED)

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager")
    def test_connects_with_pinned_ip_host_header_and_tls_sni(self, mock_pool_cls):
        mock_pool = MagicMock()
        mock_response = MagicMock(status=200, headers={"Content-Length": "1024"})
        mock_response.stream.return_value = [b"data"]
        mock_pool.request.return_value = mock_response
        mock_pool_cls.return_value = mock_pool

        self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")

        pool_kwargs = mock_pool_cls.call_args.kwargs
        self.assertEqual(pool_kwargs["server_hostname"], "example.com")
        self.assertEqual(pool_kwargs["assert_hostname"], "example.com")
        args, kwargs = mock_pool.request.call_args
        actual_url = args[1] if len(args) > 1 else kwargs["url"]
        self.assertTrue(actual_url.startswith("https://93.184.216.34"))
        self.assertEqual(kwargs["headers"]["Host"], "example.com")

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_maps_timeout_to_domain_error(self, mock_request):
        mock_request.side_effect = urllib3.exceptions.ConnectTimeoutError()
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.TIMEOUT)
        self.assertEqual(
            ctx.exception.details["exception_type"], "ConnectTimeoutError"
        )

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    def test_does_not_leak_url_secrets_in_error(self, mock_request):
        class LeakyException(Exception):
            def __str__(self):
                return "Failed connection to https://example.com?token=super_secret"

        mock_request.side_effect = LeakyException()
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NETWORK_ERROR)
        self.assertNotIn("super_secret", str(ctx.exception))
        self.assertNotIn("super_secret", str(ctx.exception.details))

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    @patch("builtins.open")
    def test_maps_enospc_to_disk_full(self, mock_open, mock_request):
        mock_response = MagicMock(status=200, headers={"Content-Length": "1024"})
        mock_response.stream.return_value = [b"chunk1"]
        mock_request.return_value = mock_response
        mock_file = MagicMock()
        mock_file.write.side_effect = OSError(errno.ENOSPC, "No space left")
        mock_open.return_value.__enter__.return_value = mock_file
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.DISK_FULL)
        self.assertEqual(ctx.exception.details["exception_type"], "OSError")

    @patch("core.media_import.adapters.direct_http_adapter.urllib3.PoolManager.request")
    @patch("builtins.open")
    def test_maps_eacces_to_permission_denied(self, mock_open, mock_request):
        mock_response = MagicMock(status=200, headers={"Content-Length": "1024"})
        mock_request.return_value = mock_response
        mock_open.side_effect = OSError(errno.EACCES, "Permission denied")
        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.mock_target, self.temp_dir.name + "/out.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.PERMISSION_DENIED)
        self.assertEqual(ctx.exception.details["exception_type"], "OSError")


if __name__ == "__main__":
    unittest.main()
