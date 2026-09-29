import ast
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

    def test_active_spec_excludes_curl_cffi(self):
        spec = Path(__file__).resolve().parents[1] / "build" / "ai_subtitle_studio.spec"
        tree = ast.parse(spec.read_text(encoding="utf-8"), filename=str(spec))
        analyses = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "Analysis"
        ]
        self.assertEqual(len(analyses), 1)
        excludes = next(kw.value for kw in analyses[0].keywords if kw.arg == "excludes")
        self.assertIn("curl_cffi", ast.literal_eval(excludes))


if __name__ == "__main__":
    unittest.main()
