import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import RecoveryContext, RecoveryWorkingState
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker


class TestRecoveryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp_dir) / "sessions"
        self.quarantine_dir = Path(self.temp_dir) / "quarantine"
        self.sessions_dir.mkdir()
        self.quarantine_dir.mkdir()
        self.tracker = MagicMock(spec=RevisionTracker)
        self.tracker.is_dirty = False
        self.tracker.edit_revision = 0
        self.tracker.snapshot_revision = 0
        self.tracker.last_saved_revision = 0
        self.tracker.last_clean_revision = 0
        self.manager = RecoveryManager(
            self.sessions_dir,
            self.quarantine_dir,
            self.tracker,
            AtomicSnapshotStore(),
            RecoveryValidator(),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def context(self, session_id: str) -> RecoveryContext:
        return RecoveryContext(
            project_id="project-1",
            project_file_path="",
            video_path="",
            source_fingerprint="abc",
            source_modified_at=0.0,
            session_id=session_id,
        )

    def make_state(self, session_id: str, revision: int) -> RecoveryWorkingState:
        return RecoveryWorkingState(
            schema_version=2.0,
            session_id=session_id,
            project_id="project-1",
            project_file_path="",
            video_path="",
            source_fingerprint="abc",
            edit_revision=revision,
            segments=[],
            workspace_state={},
        )

    def test_create_session_writes_manifest_and_lock_only(self):
        session = self.manager.create_session(self.context("new-session"))

        self.assertEqual(
            {path.name for path in session.directory.iterdir()},
            {"active.lock", "manifest.json"},
        )

    def test_create_session_preserves_null_project_id(self):
        session = self.manager.create_session(
            RecoveryContext(None, "", "", "abc", 0.0, session_id="no-project")
        )

        self.assertIsNone(
            self.manager.snapshot_store.read_json(session.directory / "manifest.json")[
                "project_id"
            ]
        )

    def test_tc90_write_snapshot_skips_without_revision_delta(self):
        session = self.manager.create_session(self.context("delta-session"))
        self.assertFalse(
            self.manager.write_snapshot(self.make_state("delta-session", 0))
        )
        self.assertFalse((session.directory / "snapshot.json").exists())

        self.tracker.is_dirty = True
        self.tracker.edit_revision = 1
        self.assertTrue(self.manager.write_snapshot(self.make_state("delta-session", 1)))
        self.assertTrue((session.directory / "snapshot.json").exists())
        self.tracker.record_snapshot_success.assert_called_once_with(1)

    def test_tc92_candidate_formula_filters_nonrecoverable_sessions(self):
        unlocked = self.manager.create_session(self.context("unlocked"))
        (unlocked.directory / "active.lock").unlink()
        self.manager.create_session(self.context("without-snapshot"))
        session = self.manager.create_session(self.context("candidate"))
        self.tracker.is_dirty = True
        self.tracker.edit_revision = 5
        self.assertTrue(self.manager.write_snapshot(self.make_state("candidate", 5)))

        manifest_path = session.directory / "manifest.json"
        manifest = self.manager.snapshot_store.read_json(manifest_path)
        for revision in ("last_saved_revision", "last_clean_revision"):
            manifest[revision] = 5
            self.manager.snapshot_store.write_json_atomic(manifest_path, manifest)
            self.assertEqual(self.manager.scan_candidates(), [])

        manifest["last_saved_revision"] = 2
        manifest["last_clean_revision"] = 2
        self.manager.snapshot_store.write_json_atomic(manifest_path, manifest)
        candidates = self.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].directory, session.directory)
        self.assertTrue(session.directory.is_dir())

    def test_tc93_corrupt_session_is_quarantined(self):
        session = self.manager.create_session(self.context("corrupt"))
        (session.directory / "snapshot.json").write_text("{bad json", encoding="utf-8")
        quarantines = []
        self.manager.session_quarantined.connect(lambda *args: quarantines.append(args))

        self.assertEqual(self.manager.scan_candidates(), [])
        self.assertFalse(session.directory.exists())
        self.assertEqual(len(list(self.quarantine_dir.iterdir())), 1)
        self.assertEqual(quarantines[0][0], "corrupt")

    def test_tc94_source_mismatch_is_valid_and_not_quarantined(self):
        session = self.manager.create_session(self.context("source-mismatch"))
        self.tracker.is_dirty = True
        self.tracker.edit_revision = 5
        self.assertTrue(
            self.manager.write_snapshot(self.make_state("source-mismatch", 5))
        )

        candidate = self.manager.scan_candidates()[0]
        result = self.manager.validate_candidate(candidate, actual_source_info=None)
        self.assertTrue(result.is_valid)
        self.assertFalse(result.source_matches)
        self.assertEqual(result.source_reason, "SOURCE_MISSING")
        self.assertTrue(session.directory.exists())
        self.assertEqual(list(self.quarantine_dir.iterdir()), [])

    def test_manifest_failure_restores_previous_snapshot(self):
        session = self.manager.create_session(self.context("manifest-failure"))
        self.tracker.is_dirty = True
        self.tracker.edit_revision = 1
        self.assertTrue(
            self.manager.write_snapshot(self.make_state("manifest-failure", 1))
        )

        original_write = self.manager.snapshot_store.write_json_atomic

        def fail_manifest(path, payload):
            if path.name == "manifest.json":
                raise OSError("manifest failed")
            original_write(path, payload)

        self.manager.snapshot_store.write_json_atomic = fail_manifest
        self.tracker.edit_revision = 2
        self.assertFalse(
            self.manager.write_snapshot(self.make_state("manifest-failure", 2))
        )

        candidates = self.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 1)
        self.assertTrue(session.directory.exists())

    def test_write_snapshot_rejects_stale_or_wrong_session_state(self):
        session = self.manager.create_session(self.context("active"))
        self.tracker.is_dirty = True
        self.tracker.edit_revision = 2

        self.assertFalse(self.manager.write_snapshot(self.make_state("active", 1)))
        self.assertFalse(self.manager.write_snapshot(self.make_state("other", 2)))
        self.assertFalse((session.directory / "snapshot.json").exists())
        self.tracker.record_snapshot_success.assert_not_called()

    def test_quarantine_move_failure_keeps_session_and_does_not_emit(self):
        session = self.manager.create_session(self.context("move-failure"))
        quarantines = []
        self.manager.session_quarantined.connect(lambda *args: quarantines.append(args))

        with patch("core.recovery.recovery_manager.shutil.move", side_effect=OSError):
            result = self.manager.quarantine_session("move-failure", "corrupt")

        self.assertEqual(result, session.directory)
        self.assertTrue(session.directory.exists())
        self.assertEqual(quarantines, [])


if __name__ == "__main__":
    unittest.main()
