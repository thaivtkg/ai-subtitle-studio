import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore


class TestAtomicSnapshotStore(unittest.TestCase):
    def test_write_json_atomic_replaces_target_cleanly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.json"

            AtomicSnapshotStore().write_json_atomic(
                target, {"revision": 1, "data": "test"}
            )

            self.assertEqual(json.loads(target.read_text("utf-8"))["revision"], 1)
            self.assertFalse(target.with_suffix(".tmp").exists())

    def test_replace_failure_preserves_previous_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.json"
            target.write_text('{"revision": 1}', encoding="utf-8")

            with patch(
                "core.recovery.atomic_snapshot_store.os.replace",
                side_effect=OSError("Disk replace failed"),
            ):
                with self.assertRaises(OSError):
                    AtomicSnapshotStore().write_json_atomic(target, {"revision": 2})

            self.assertEqual(json.loads(target.read_text("utf-8"))["revision"], 1)

    def test_json_dump_failure_cleans_up_tmp_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.json"

            with self.assertRaises(TypeError):
                AtomicSnapshotStore().write_json_atomic(
                    target, {"revision": 2, "bad_data": {1, 2, 3}}
                )

            self.assertFalse(target.with_suffix(".tmp").exists())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
