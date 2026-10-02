import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:
    import yt_dlp
except ImportError:
    class DownloadError(Exception):
        pass

    yt_dlp = MagicMock()
    yt_dlp.utils = SimpleNamespace(DownloadError=DownloadError)
    sys.modules["yt_dlp"] = yt_dlp

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.network_safety import NetworkSafetyPolicy, SafeResolvedTarget, SafeSocketContext

from core.media_import.adapters.yt_dlp_adapter import YtDlpAdapter

try:
    from core.media_import.source_guard import SourceGuard
except (ImportError, ModuleNotFoundError, OSError):
    SourceGuard = None


class TestYtDlpSSRFClosure(unittest.TestCase):
    def setUp(self):
        self.safety_policy = NetworkSafetyPolicy()
        self.adapter = YtDlpAdapter(safety_policy=self.safety_policy)
        self.target = SafeResolvedTarget(
            original_url="https://public-video.example.com/watch?v=test",
            scheme="https",
            hostname="public-video.example.com",
            port=443,
            resolved_ips=("93.184.216.34",),
        )

    @patch("yt_dlp.YoutubeDL")
    def test_tc131_ytdlp_blocks_rebinding_or_nested_internal_ip(self, mock_ydl_cls):
        dest = tempfile.mktemp(suffix=".mp4")
        mock_ydl = MagicMock()

        def fake_extract(url, download=True):
            import socket

            socket.getaddrinfo("evil-redirect.example.com", 443)
            return {"filepath": dest}

        mock_ydl.extract_info.side_effect = fake_extract
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        with patch("socket.getaddrinfo") as mock_gai:
            import socket

            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))
            ]
            with self.assertRaises(MediaImportError) as ctx:
                self.adapter.download(self.target, dest)

        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)
        self.assertIn("blocked", str(ctx.exception).lower())

    @patch("yt_dlp.YoutubeDL")
    def test_ytdlp_adapter_forces_direct_connection(self, mock_ydl_cls):
        dest = Path(tempfile.mktemp(suffix=".mp4"))
        dest.write_bytes(b"data")
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "filepath": str(dest), "ext": "mp4", "extractor": "test"
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        try:
            self.adapter.download(self.target, dest)
            opts = mock_ydl_cls.call_args.kwargs["params"]
            self.assertEqual(opts.get("proxy"), "")
            self.assertTrue(opts.get("hls_prefer_native"))
        finally:
            dest.unlink(missing_ok=True)

    @patch("yt_dlp.YoutubeDL")
    def test_ytdlp_adapter_maps_wrapped_blocked_gaierror(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(
            "ERROR: Unable to download API page: <urlopen error [Errno -2] "
            "Blocked connection to unsafe IP: 169.254.169.254>"
        )
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl

        with self.assertRaises(MediaImportError) as ctx:
            self.adapter.download(self.target, tempfile.mktemp(suffix=".mp4"))

        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)


class TestSourceGuard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source_file = self.root / "source.mp4"
        self.source_file.write_bytes(b"media-content")
        self.guard = SourceGuard()

    def test_source_guard_verifies_path_confinement_and_integrity(self):
        allowed_root = self.root / "bundle"
        valid_path = allowed_root / "media" / "source.mp4"
        valid_path.parent.mkdir(parents=True, exist_ok=True)
        valid_path.write_bytes(b"data")

        self.assertTrue(self.guard.is_confined(valid_path, allowed_root))
        traversal_path = allowed_root / ".." / "outside.mp4"
        self.assertFalse(self.guard.is_confined(traversal_path, allowed_root))
        self.assertTrue(self.guard.verify_integrity(valid_path))


class TestNetworkSafetyConcurrencyAndGuard(unittest.TestCase):
    def test_safe_socket_context_guards_child_threads_globally(self):
        policy = NetworkSafetyPolicy()
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 443))
            ]
            with SafeSocketContext(policy):
                result_error = []

                def child_task():
                    try:
                        socket.getaddrinfo("evil-redirect.com", 443)
                    except Exception as exc:
                        result_error.append(exc)

                thread = threading.Thread(target=child_task)
                thread.start()
                thread.join()

        self.assertEqual(len(result_error), 1)
        self.assertIsInstance(result_error[0], socket.gaierror)


if __name__ == "__main__":
    unittest.main()
