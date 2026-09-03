import unittest
from pathlib import Path


class TestPackagingConstraints(unittest.TestCase):
    def test_yt_dlp_is_available_in_runtime(self):
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            self.fail("CRITICAL: 'yt_dlp' package is missing from the runtime environment.")

    def test_curl_cffi_is_strictly_excluded(self):
        try:
            import curl_cffi  # noqa: F401
        except ImportError:
            return
        self.fail(
            "SECURITY BREACH: 'curl_cffi' is present in the environment. "
            "It must be excluded to maintain the SSRF boundary."
        )

    def test_spec_file_excludes_curl_cffi(self):
        spec_files = list(Path(".").glob("*.spec"))
        if not spec_files:
            self.skipTest("No .spec file found in project root")
        for spec in spec_files:
            self.assertIn(
                "curl_cffi",
                spec.read_text(encoding="utf-8"),
                f"File {spec.name} is missing curl_cffi exclusion",
            )


if __name__ == "__main__":
    unittest.main()
