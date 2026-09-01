import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime.runtime_paths import RuntimePaths
from core.project.source_fingerprint import generate_source_info


class TestRecoveryPaths(unittest.TestCase):
    def test_recovery_paths_live_under_user_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                root = RuntimePaths.get_user_data_dir()
                self.assertEqual(RuntimePaths.get_recovery_dir(), root / "recovery")
                self.assertEqual(
                    RuntimePaths.get_recovery_sessions_dir(),
                    root / "recovery" / "sessions",
                )
                self.assertEqual(
                    RuntimePaths.get_recovery_quarantine_dir(),
                    root / "recovery" / "quarantine",
                )

    def test_ensure_user_data_dirs_creates_recovery_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                RuntimePaths.ensure_user_data_dirs()
                self.assertTrue(RuntimePaths.get_recovery_sessions_dir().is_dir())
                self.assertTrue(RuntimePaths.get_recovery_quarantine_dir().is_dir())


class TestSourceFingerprint(unittest.TestCase):
    def test_shared_fingerprint_matches_project_source_shape(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"subtitle-source" * 64)
            path = handle.name
        try:
            info = generate_source_info(path)
            self.assertEqual(info.path, path)
            self.assertEqual(info.filename, os.path.basename(path))
            self.assertGreater(info.size_bytes, 0)
            self.assertEqual(len(info.fingerprint), 64)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
