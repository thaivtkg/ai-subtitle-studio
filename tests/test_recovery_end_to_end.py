import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import RecoveryContext, RecoveryWorkingState
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker


class TestRecoveryEndToEnd(unittest.TestCase):
    def test_recovery_handoff_commits_new_session_before_discarding_old(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        tracker = MagicMock(spec=RevisionTracker)
        tracker.is_dirty = True
        tracker.edit_revision = 1
        tracker.snapshot_revision = 0
        tracker.last_saved_revision = 0
        tracker.last_clean_revision = 0
        tracker.record_snapshot_success.side_effect = lambda revision: setattr(
            tracker, "snapshot_revision", revision
        )
        manager = RecoveryManager(
            root / "sessions", root / "quarantine", tracker, AtomicSnapshotStore(), RecoveryValidator()
        )
        old = manager.create_session(RecoveryContext("p", "project", "video", "fp", 0.0, session_id="old"))
        state = RecoveryWorkingState(2.0, "old", "p", "project", "video", "fp", 1)
        self.assertTrue(manager.write_snapshot(state))
        candidate = manager.scan_candidates()[0]
        new = manager.handoff_recovered_state(
            candidate, state, RecoveryContext("p", "project", "video", "fp", 0.0, session_id="new")
        )
        self.assertFalse(old.directory.exists())
        self.assertTrue((new.directory / "active.lock").exists())
        self.assertTrue((new.directory / "snapshot.json").exists())

    def test_save_then_clean_shutdown_removes_recovery_artifacts(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        tracker = MagicMock(spec=RevisionTracker)
        tracker.is_dirty = True
        tracker.edit_revision = 1
        tracker.snapshot_revision = 0
        tracker.last_saved_revision = 0
        tracker.last_clean_revision = 0
        tracker.record_snapshot_success.side_effect = lambda revision: setattr(
            tracker, "snapshot_revision", revision
        )
        tracker.record_explicit_save_success.side_effect = lambda: self._save(tracker)
        manager = RecoveryManager(
            root / "sessions", root / "quarantine", tracker, AtomicSnapshotStore(), RecoveryValidator()
        )
        context = RecoveryContext("p", "project", "video", "fp", 0.0, session_id="e2e")
        session = manager.create_session(context)
        state = RecoveryWorkingState(2.0, "e2e", "p", "project", "video", "fp", 1)
        self.assertTrue(manager.write_snapshot(state))
        manager.record_explicit_save()
        manager.finalize_clean_shutdown()
        self.assertFalse(session.directory.exists())

    @staticmethod
    def _save(tracker):
        tracker.last_saved_revision = tracker.edit_revision
        tracker.last_clean_revision = tracker.edit_revision
        tracker.is_dirty = False


if __name__ == "__main__":
    unittest.main()
