import tempfile
import unittest
from pathlib import Path

from core.demo_capture.artifact_writer import ArtifactWriter
from core.demo_capture.models import OutputFormat, OutputSpec


class TestArtifactWriterC4(unittest.TestCase):
    def test_tc227_commit_atomically_replaces_existing_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = root / "demo.png"
            final.write_bytes(b"old")
            staged = root / ".staging" / "demo.tmp"
            staged.parent.mkdir()
            staged.write_bytes(b"new")
            ArtifactWriter(root).commit(staged, OutputSpec("demo.png", OutputFormat.PNG))
            self.assertEqual(final.read_bytes(), b"new")
            self.assertFalse(staged.exists())

    def test_tc228_failed_commit_keeps_old_final_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = root / "demo.png"
            final.write_bytes(b"old")
            with self.assertRaises(Exception):
                ArtifactWriter(root).commit(root / ".staging" / "missing", OutputSpec("demo.png", OutputFormat.PNG))
            self.assertEqual(final.read_bytes(), b"old")

    def test_tc229_rejects_staged_and_final_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = ArtifactWriter(root)
            staged = root / "staged.tmp"
            staged.write_bytes(b"data")
            with self.assertRaises(Exception):
                writer.commit(staged, OutputSpec("../escape.png", OutputFormat.PNG))
            outside = root.parent / "outside.tmp"
            outside.write_bytes(b"data")
            try:
                with self.assertRaises(Exception):
                    writer.commit(outside, OutputSpec("safe.png", OutputFormat.PNG))
            finally:
                outside.unlink()

    def test_tc230_cleanup_is_safe_for_success_and_abort(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / ".staging" / "demo.tmp"
            staged.parent.mkdir()
            staged.write_bytes(b"data")
            ArtifactWriter(root).cleanup(staged)
            self.assertFalse(staged.exists())
            ArtifactWriter(root).cleanup(staged)


if __name__ == "__main__":
    unittest.main()
