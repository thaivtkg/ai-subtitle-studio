import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.tutorial.progress_store import GuideProgressStatus, TourProgressStore


class TestTourProgressStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "tutorial_progress.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tc166_round_trip_and_statuses(self):
        store = TourProgressStore(self.path)
        self.assertTrue(store.mark_completed("done", 2))
        self.assertTrue(store.mark_dismissed("dismissed", 1))
        self.assertFalse(list(self.path.parent.glob("*.tmp.*")))

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("updated_at", raw)
        self.assertIn("completed_at", raw["progress"]["done"])
        self.assertNotIn("dismissed_at", raw["progress"]["done"])
        self.assertIn("dismissed_at", raw["progress"]["dismissed"])

        restored = TourProgressStore(self.path)
        self.assertEqual(restored.status("done", 2).status, GuideProgressStatus.COMPLETED)
        self.assertEqual(restored.status("dismissed", 1).status, GuideProgressStatus.DISMISSED)

    def test_tc167_corrupt_json_is_quarantined(self):
        self.path.write_text("{broken", encoding="utf-8")
        store = TourProgressStore(self.path)
        self.assertEqual(store.status("g", 1).status, GuideProgressStatus.NOT_STARTED)
        self.assertFalse(self.path.exists())
        self.assertEqual(len(list(self.path.parent.glob("tutorial_progress.corrupt.*.json"))), 1)

        self.path.write_text("[]", encoding="utf-8")
        store = TourProgressStore(self.path)
        self.assertEqual(store.status("g", 1).status, GuideProgressStatus.NOT_STARTED)
        self.assertFalse(self.path.exists())

    def test_tc168_replace_failure_keeps_snapshot_and_bytes(self):
        store = TourProgressStore(self.path)
        self.assertTrue(store.mark_completed("g", 1))
        old_bytes = self.path.read_bytes()
        with patch("core.tutorial.progress_store.os.replace", side_effect=OSError("disk")):
            self.assertFalse(store.mark_completed("g", 2))
        self.assertEqual(store.status("g", 2).status, GuideProgressStatus.OUTDATED)
        self.assertEqual(self.path.read_bytes(), old_bytes)

    def test_tc169_quarantine_failure_is_read_only(self):
        self.path.write_text("{broken", encoding="utf-8")
        original = self.path.read_bytes()
        with patch("core.tutorial.progress_store.os.replace", side_effect=OSError("rename")):
            store = TourProgressStore(self.path)
            self.assertEqual(store.status("g", 1).status, GuideProgressStatus.UNKNOWN)
            self.assertFalse(store.mark_completed("g", 1))
        self.assertEqual(self.path.read_bytes(), original)

    def test_tc170_future_schema_is_read_only(self):
        self.path.write_text(json.dumps({"schema_version": 99, "guides": {}}), encoding="utf-8")
        original = self.path.read_bytes()
        store = TourProgressStore(self.path)
        self.assertEqual(store.status("g", 1).status, GuideProgressStatus.UNKNOWN)
        self.assertFalse(store.mark_completed("g", 1))
        self.assertEqual(self.path.read_bytes(), original)

    def test_tc171_v0_migrates_only_on_explicit_write(self):
        self.path.write_text(json.dumps({"schema_version": 0, "completed_guides": {"g": 1}}), encoding="utf-8")
        original = self.path.read_bytes()
        store = TourProgressStore(self.path)
        self.assertEqual(store.status("g", 1).status, GuideProgressStatus.COMPLETED)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(store.mark_dismissed("new", 1))
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_tc172_older_content_is_outdated(self):
        store = TourProgressStore(self.path)
        self.assertTrue(store.mark_completed("g", 1))
        self.assertEqual(store.status("g", 2).status, GuideProgressStatus.OUTDATED)
        self.assertFalse(store.is_completed("g", 2))

    def test_tc173_newer_stored_content_is_not_downgraded(self):
        store = TourProgressStore(self.path)
        self.assertTrue(store.mark_completed("g", 3))
        before = self.path.read_bytes()
        self.assertEqual(store.status("g", 2).status, GuideProgressStatus.COMPLETED_NEWER_VERSION)
        self.assertEqual(store.status("g", 2).content_version, 3)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
