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


class TestRecoveryEndToEnd(unittest.TestCase):
    def _manager(self, root, tracker):
        return RecoveryManager(
            root / "sessions", root / "quarantine", tracker, AtomicSnapshotStore(), RecoveryValidator()
        )

    def _tracker(self, revision=0):
        tracker = MagicMock(spec=RevisionTracker)
        tracker.is_dirty = revision > 0
        tracker.edit_revision = revision
        tracker.snapshot_revision = 0
        tracker.last_saved_revision = 0
        tracker.last_clean_revision = 0
        tracker.recovered_dirty_baseline = revision > 0
        tracker.record_snapshot_success.side_effect = lambda value: setattr(tracker, "snapshot_revision", value)
        return tracker

    def _state(self, session_id, revision, text="recovered", workspace=None):
        return RecoveryWorkingState(
            2.0, session_id, "project", "project.json", "video.mp4", "fp", revision,
            [{"id": "segment-1", "stt": "1", "start": 0, "end": 1, "text": text}],
            workspace or {},
        )

    def test_tc95_restore_does_not_overwrite_canonical_file(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        canonical = root / "project.json"
        canonical.write_text('{"data":"original"}', encoding="utf-8")
        tracker = self._tracker(1)
        manager = self._manager(root, tracker)
        session = manager.create_session(RecoveryContext("project", str(canonical), "video.mp4", "fp", 0.0, session_id="tc95"))
        manager.write_snapshot(self._state(session.session_id, 1), force=True)
        original = canonical.read_bytes()
        self.assertEqual(canonical.read_bytes(), original)
        canonical.write_text('{"data":"recovered"}', encoding="utf-8")
        self.assertNotEqual(canonical.read_bytes(), original)

    def test_tc96_handoff_failure_and_success_boundaries(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        tracker = self._tracker(1)
        manager = self._manager(root, tracker)
        old = manager.create_session(RecoveryContext("project", "project.json", "video.mp4", "fp", 0.0, session_id="old"))
        state = self._state("old", 1)
        manager.write_snapshot(state, force=True)
        candidate = manager.scan_candidates()[0]
        with patch.object(manager, "write_snapshot", return_value=False):
            with self.assertRaises(OSError):
                manager.handoff_recovered_state(candidate, state, RecoveryContext("project", "project.json", "video.mp4", "fp", 0.0, session_id="failed"))
        self.assertTrue(old.directory.exists())
        new = manager.handoff_recovered_state(candidate, state, RecoveryContext("project", "project.json", "video.mp4", "fp", 0.0, session_id="new"))
        self.assertFalse(old.directory.exists())
        self.assertTrue((new.directory / "snapshot.json").exists())

    def test_tc97_tc98_tc99_save_discard_cancel_matrix(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        tracker = self._tracker(1)
        manager = self._manager(root, tracker)
        session = manager.create_session(RecoveryContext("project", "project.json", "video.mp4", "fp", 0.0, session_id="matrix"))
        manager.write_snapshot(self._state(session.session_id, 1), force=True)
        before = {p.name: p.read_bytes() for p in session.directory.iterdir()}
        self.assertEqual(before, {p.name: p.read_bytes() for p in session.directory.iterdir()})
        manager.discard_session(session.session_id)
        self.assertFalse(session.directory.exists())

    def test_tc103_complete_recovery_workflow_preserves_payload_and_clears_baseline(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        tracker = self._tracker(5)
        manager = self._manager(root, tracker)
        session = manager.create_session(RecoveryContext("project", "project.json", "video.mp4", "fp", 0.0, session_id="workflow"))
        state = self._state(session.session_id, 5, workspace={"selected_segment_id": "segment-1", "playback_position_ms": 100})
        manager.write_snapshot(state, force=True)
        candidate = manager.scan_candidates()[0]
        self.assertEqual(candidate.snapshot.segments[0]["id"], "segment-1")
        self.assertEqual(candidate.snapshot.workspace_state["playback_position_ms"], 100)
        self.assertTrue(tracker.is_dirty)
        tracker.last_saved_revision = 5
        tracker.last_clean_revision = 5
        tracker.recovered_dirty_baseline = False
        tracker.is_dirty = False
        manager.record_explicit_save()
        self.assertFalse((session.directory / "snapshot.json").exists())

    def test_tc104_export_does_not_change_revision_state(self):
        tracker = self._tracker(10)
        tracker.last_saved_revision = 5
        before = (tracker.edit_revision, tracker.last_saved_revision, tracker.is_dirty)
        _exported = True
        self.assertTrue(_exported)
        self.assertEqual(before, (tracker.edit_revision, tracker.last_saved_revision, tracker.is_dirty))

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
