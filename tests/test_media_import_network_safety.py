import socket
import unittest
from unittest.mock import patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.network_safety import NetworkSafetyPolicy, SafeResolvedTarget
from core.media_import.url_classifier import MediaURLType, URLClassifier


class TestNetworkSafetyPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = NetworkSafetyPolicy()

    # --- 1. Scheme & Structure Validation ---

    def test_rejects_disallowed_schemes(self):
        blocked_urls = [
            "file:///etc/passwd",
            "ftp://example.com/video.mp4",
            "smb://server/share/file.mp4",
            "data:text/plain;base64,SGVsbG8=",
            "javascript:alert(1)",
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(MediaImportError) as ctx:
                    self.policy.validate_url(url)
                self.assertIn(
                    ctx.exception.code,
                    [MediaImportErrorCode.UNSAFE_URL, MediaImportErrorCode.INVALID_URL],
                )

    def test_rejects_missing_or_invalid_host(self):
        for url in [
            "http://",
            "https:///video.mp4",
            "not_a_url",
            "http://example.com:99999/",
            "http://8.8.8.8:0/",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(MediaImportError) as ctx:
                    self.policy.validate_url(url)
                self.assertEqual(ctx.exception.code, MediaImportErrorCode.INVALID_URL)

    def test_preserves_valid_explicit_port(self):
        target = self.policy.validate_url("https://8.8.8.8:8443/media.mp4")
        self.assertEqual(target.port, 8443)

    def test_pinned_target_representation_does_not_expose_query_or_fragment(self):
        target = SafeResolvedTarget(
            original_url="https://example.com/media.mp4?token=SECRET#private",
            scheme="https",
            hostname="example.com",
            port=443,
            resolved_ips=("93.184.216.34",),
        )
        self.assertNotIn("SECRET", repr(target))
        self.assertNotIn("private", str(target))

    def test_rejects_embedded_credentials(self):
        # Sprint 12: URL auth is not allowed
        url = "https://user:password@example.com/video.mp4"
        with self.assertRaises(MediaImportError) as ctx:
            self.policy.validate_url(url)
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)

    # --- 2. IP Blacklisting ---

    def test_rejects_private_and_reserved_ips(self):
        dangerous_ips = [
            "127.0.0.1",           # Loopback
            "10.0.0.1",            # RFC 1918 Private
            "172.16.0.1",          # RFC 1918 Private
            "192.168.1.1",         # RFC 1918 Private
            "169.254.169.254",     # Link-local / Cloud Metadata
            "224.0.0.1",           # Multicast
            "0.0.0.0",             # Unspecified
            "100.64.0.1",          # CGNAT (100.64.0.0/10)
        ]
        for ip in dangerous_ips:
            with self.subTest(ip=ip):
                with self.assertRaises(MediaImportError) as ctx:
                    self.policy.validate_url(f"http://{ip}/stream.mp4")
                self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)

    def test_rejects_ipv4_mapped_ipv6(self):
        # Phải unwrap được IPv4 ẩn bên trong IPv6 map
        mapped_ips = [
            "[::ffff:127.0.0.1]",
            "[::ffff:192.168.1.1]",
        ]
        for ip in mapped_ips:
            with self.subTest(ip=ip):
                with self.assertRaises(MediaImportError) as ctx:
                    self.policy.validate_url(f"http://{ip}/stream.mp4")
                self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)

    def test_rejects_other_non_public_ipv4_and_ipv6_ranges(self):
        dangerous_hosts = [
            "240.0.0.1",
            "[::1]",
            "[::]",
            "[fe80::1]",
            "[fc00::1]",
            "[ff02::1]",
            "[::ffff:169.254.169.254]",
        ]
        for host in dangerous_hosts:
            with self.subTest(host=host):
                with self.assertRaises(MediaImportError) as ctx:
                    self.policy.validate_url(f"https://{host}/stream.mp4")
                self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)

    # --- 3. DNS Resolution & TOCTOU Prevention ---

    @patch("socket.getaddrinfo")
    def test_rejects_mixed_dns_resolution(self, mock_getaddrinfo):
        # Mô phỏng domain có cả IP public và IP private (fc00::1)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fc00::1", 443, 0, 0)),
        ]
        with self.assertRaises(MediaImportError) as ctx:
            self.policy.validate_url("https://mixed.attacker.com/video.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)

    @patch("socket.getaddrinfo", side_effect=UnicodeError("label empty or too long"))
    def test_maps_malformed_dns_hostname_to_invalid_url(self, _mock_getaddrinfo):
        with self.assertRaises(MediaImportError) as ctx:
            self.policy.validate_url(f"https://{'a' * 64}.com/video.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.INVALID_URL)

    @patch("socket.getaddrinfo")
    def test_accepts_valid_domain_and_returns_pinned_target(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0),
            ),
        ]
        target = self.policy.validate_url("https://example.com/media.mp4")
        self.assertIsInstance(target, SafeResolvedTarget)
        self.assertEqual(target.original_url, "https://example.com/media.mp4")
        self.assertEqual(target.scheme, "https")
        self.assertEqual(target.hostname, "example.com")
        self.assertEqual(target.port, 443)
        self.assertEqual(
            target.resolved_ips,
            ("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"),
        )

    @patch("socket.getaddrinfo")
    def test_redirect_revalidates_dns_and_rejects_private_target(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443)),
        ]
        with self.assertRaises(MediaImportError) as ctx:
            self.policy.validate_redirect("https://metadata.attacker/redirected.mp4")
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.UNSAFE_URL)


class TestURLClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = URLClassifier()

    def test_recognizes_direct_media_with_encoded_path_and_query(self):
        direct_urls = [
            "https://site/video.mp4",
            "https://site/path/file%20name.MP4?token=123#frag",
            "http://site/audio.m4a",
            "https://site/movie.webm",
            "https://site/movie.mkv",
            "https://site/movie.mov",
            "https://site/movie.m4v",
            "https://site/audio.mp3",
            "https://site/audio.wav",
            "https://site/audio.opus",
        ]
        for url in direct_urls:
            with self.subTest(url=url):
                self.assertEqual(self.classifier.classify(url), MediaURLType.DIRECT_MEDIA)

    def test_leaves_webpages_as_non_direct(self):
        web_urls = [
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://site/watch?id=file.mp4",
            "https://site/article/",
            "http://[::1",
        ]
        for url in web_urls:
            with self.subTest(url=url):
                self.assertEqual(
                    self.classifier.classify(url),
                    MediaURLType.PAGE_OR_EXTRACTOR,
                )

    def test_recognizes_audio_and_video_content_type_hints(self):
        self.assertTrue(
            self.classifier.is_obvious_direct_media(
                "https://site/download",
                "video/mp4; charset=binary",
            )
        )
        self.assertTrue(
            self.classifier.is_obvious_direct_media("https://site/download", "audio/mpeg")
        )
        self.assertFalse(
            self.classifier.is_obvious_direct_media("https://site/article", "text/html")
        )


if __name__ == "__main__":
    unittest.main()
