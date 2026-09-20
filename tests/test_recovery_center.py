import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.canonical_save_coordinator import CanonicalSaveCoordinator
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import RecoveryContext, RecoveryWorkingState
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker


class RecoveryCenterContract(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.sessions = self.root / "sessions"
        self.quarantine = self.root / "quarantine"
        self.sessions.mkdir()
        self.quarantine.mkdir()
        self.tracker = MagicMock(spec=RevisionTracker)
        self.tracker.is_dirty = False
        self.tracker.edit_revision = 0
        self.tracker.snapshot_revision = 0
        self.tracker.last_saved_revision = 0
        self.tracker.last_clean_revision = 0
        self.tracker.record_snapshot_success.side_effect = lambda revision: setattr(
            self.tracker, "snapshot_revision", revision
        )
        self.manager = RecoveryManager(
            self.sessions,
            self.quarantine,
            self.tracker,
            AtomicSnapshotStore(),
            RecoveryValidator(),
        )

    def tearDown(self):
        shutil.rmtree(self.root)

    def context(self, session_id, project_id="project-a", project_root=None, video="shared.mp4"):
        return RecoveryContext(
            project_id,
            project_root or str(self.root / f"{project_id}.ai-subtitle"),
            video,
            f"fingerprint-{project_id}",
            0.0,
            session_id=session_id,
        )

    def new_manager(self):
        return RecoveryManager(
            self.sessions,
            self.quarantine,
            self.tracker,
            AtomicSnapshotStore(),
            RecoveryValidator(),
        )

    def state(self, session_id, revision, project_id="project-a", project_root=None, video="shared.mp4"):
        return RecoveryWorkingState(
            2.0,
            session_id,
            project_id,
            project_root or str(self.root / f"{project_id}.ai-subtitle"),
            video,
            f"fingerprint-{project_id}",
            revision,
            [{"id": f"segment-{revision}", "stt": "1", "start": 0, "end": 1, "text": "recovered"}],
            {"active_page": "editor"},
            {"context": "notes", "glossary": []},
        )

    def write(self, session_id, revision, project_id="project-a", project_root=None, video="shared.mp4", manager=None):
        manager = manager or self.manager
        session = manager.create_session(
            self.context(session_id, project_id, project_root, video)
        )
        self.tracker.is_dirty = True
        self.tracker.edit_revision = revision
        self.assertTrue(
            manager.write_snapshot(
                self.state(session_id, revision, project_id, project_root, video),
                force=True,
            )
        )
        return session

    def test_RC01_valid_session_discovers_one_effective_entry(self):
        self.write("session-a", 3)
        catalog = self.new_manager()

        entries = catalog.list_recovery_entries()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].session_id, "session-a")

    def test_RC02_same_video_different_projects_remain_independent(self):
        self.write("session-a", 2, "project-a", video="same.mp4")
        self.write("session-b", 4, "project-b", video="same.mp4", manager=self.new_manager())

        entries = self.new_manager().list_recovery_entries()

        self.assertEqual({entry.project_id for entry in entries}, {"project-a", "project-b"})

    def test_RC03_identity_uses_project_id_and_root_not_video_path(self):
        self.write("session-a", 2, "project-a", str(self.root / "A.ai-subtitle"), "same.mp4")
        self.write("session-b", 3, "project-b", str(self.root / "B.ai-subtitle"), "same.mp4", manager=self.new_manager())

        entries = self.new_manager().list_recovery_entries()

        self.assertEqual(
            {(entry.project_id, entry.project_root) for entry in entries},
            {
                ("project-a", str(self.root / "A.ai-subtitle")),
                ("project-b", str(self.root / "B.ai-subtitle")),
            },
        )

    def test_RC04_ordering_does_not_depend_on_filesystem_order(self):
        self.write("z-session", 2)
        self.write("a-session", 5, manager=self.new_manager())

        entries = self.new_manager().list_recovery_entries()

        self.assertEqual([entry.session_id for entry in entries], ["a-session", "z-session"])

    def test_RC05_current_pair_is_preferred_over_rotated_pairs(self):
        session = self.write("session-a", 1)
        self.tracker.edit_revision = 2
        self.manager.write_snapshot(self.state("session-a", 2), force=True)
        self.tracker.edit_revision = 3
        self.manager.write_snapshot(self.state("session-a", 3), force=True)

        candidate = self.manager.scan_candidates()[0]

        self.assertEqual(candidate.snapshot.edit_revision, 3)
        self.assertEqual(len(self.new_manager().list_recovery_entries()), 1)
        self.assertTrue(session.directory.exists())

    def test_RC06_invalid_current_falls_back_to_previous_without_extra_entry(self):
        session = self.write("session-a", 1)
        self.tracker.edit_revision = 2
        self.manager.write_snapshot(self.state("session-a", 2), force=True)
        (session.directory / "snapshot.json").write_text("{bad", encoding="utf-8")

        candidates = self.manager.scan_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 1)
        self.assertEqual(len(self.new_manager().list_recovery_entries()), 1)

    def test_RC07_missing_pair_is_not_discovered(self):
        session = self.manager.create_session(self.context("missing"))
        (session.directory / "manifest.json").unlink()

        self.assertEqual(self.manager.scan_candidates(), [])

    def test_RC08_corrupt_pair_is_quarantined_not_healthy(self):
        session = self.manager.create_session(self.context("corrupt"))
        (session.directory / "snapshot.json").write_text("{bad", encoding="utf-8")

        self.assertEqual(self.manager.scan_candidates(), [])
        self.assertFalse(session.directory.exists())
        self.assertEqual(len(list(self.quarantine.iterdir())), 1)

    def test_RC09_unsupported_schema_is_not_discovered(self):
        session = self.write("unsupported", 2)
        payload = json.loads((session.directory / "manifest.json").read_text(encoding="utf-8"))
        payload["schema_version"] = 99
        (session.directory / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")

        self.assertEqual(self.manager.scan_candidates(), [])

    def test_RC10_source_missing_remains_visible_but_is_unlinked(self):
        self.write("missing-source", 2)
        catalog = self.new_manager()

        entries = catalog.list_recovery_entries()

        self.assertEqual(entries[0].source_status, "SOURCE_MISSING")
        self.assertTrue(entries[0].unlinked_restore_allowed)
        self.assertFalse(entries[0].linked_restore_allowed)

    def test_RC11_source_mismatch_remains_visible_but_is_unlinked(self):
        self.write("mismatch-source", 2)
        catalog = self.new_manager()

        entries = catalog.list_recovery_entries(
            source_info_by_project={"project-a": SimpleNamespace(fingerprint="other")}
        )

        self.assertEqual(entries[0].source_status, "SOURCE_MISMATCH")
        self.assertTrue(entries[0].unlinked_restore_allowed)
        self.assertFalse(entries[0].linked_restore_allowed)

    def test_RC19_source_match_is_available_and_linked(self):
        self.write("available-source", 2)
        catalog = self.new_manager()

        entries = catalog.list_recovery_entries(
            source_info_by_project={
                "project-a": SimpleNamespace(fingerprint="fingerprint-project-a")
            }
        )

        self.assertEqual(entries[0].source_status, "AVAILABLE")
        self.assertFalse(entries[0].unlinked_restore_allowed)
        self.assertTrue(entries[0].linked_restore_allowed)

    def test_RC20_lookup_uses_session_identity(self):
        self.write("stable-session", 2)
        catalog = self.new_manager()

        entry = catalog.resolve_recovery_entry("stable-session")

        self.assertIsNotNone(entry)
        self.assertEqual(entry.session_id, "stable-session")
        self.assertIsNone(catalog.resolve_recovery_entry("not-the-session"))

    def test_RC12_current_process_session_is_not_recoverable(self):
        self.write("live", 2)

        self.assertEqual(
            self.manager.list_recovery_entries(active_session_id="live"), []
        )
        self.assertEqual(
            [entry.session_id for entry in self.manager.list_recovery_entries()],
            ["live"],
        )

    def test_RC13_handoff_restores_payload_and_replaces_old_session(self):
        old = self.write("old", 4)
        candidate = self.manager.scan_candidates()[0]
        new = self.manager.handoff_recovered_state(
            candidate,
            candidate.snapshot,
            self.context("new"),
        )

        self.assertFalse(old.directory.exists())
        self.assertTrue((new.directory / "snapshot.json").exists())
        self.assertEqual(
            json.loads((new.directory / "snapshot.json").read_text(encoding="utf-8"))["segments"][0]["text"],
            "recovered",
        )

    def test_RC14_recovered_revision_is_not_immediately_canonical_save_eligible(self):
        tracker = SimpleNamespace(is_dirty=True, edit_revision=7, snapshot_revision=7)
        coordinator = CanonicalSaveCoordinator(
            revision_tracker=tracker,
            save_current_project=MagicMock(),
            scheduler=SimpleNamespace(),
            active_project_provider=lambda: object(),
        )

        self.assertTrue(coordinator.flush_now())
        coordinator.save_current_project.assert_not_called()

    def test_RC15_new_mutation_after_restore_is_canonical_save_eligible(self):
        tracker = SimpleNamespace(is_dirty=True, edit_revision=8, snapshot_revision=7)
        coordinator = CanonicalSaveCoordinator(
            revision_tracker=tracker,
            save_current_project=MagicMock(return_value=True),
            scheduler=SimpleNamespace(
                call_later=MagicMock(),
                cancel=MagicMock(),
            ),
            active_project_provider=lambda: object(),
        )

        coordinator.flush_now()

        coordinator.save_current_project.assert_called_once()

    def test_RC16_discard_removes_all_slots_and_preserves_other_session(self):
        first = self.write("first", 1)
        second = self.write("second", 2, manager=self.new_manager())

        self.manager.discard_session(first.session_id)

        self.assertFalse(first.directory.exists())
        self.assertTrue(second.directory.exists())

    def test_RC17_active_session_delete_is_refused(self):
        session = self.write("live", 2)

        self.assertFalse(
            self.manager.delete_entry(session.session_id, active_session_id="live")
        )
        self.assertTrue(session.directory.exists())

        stale = self.write("stale", 3, manager=self.new_manager())
        self.assertTrue(self.manager.delete_entry(stale.session_id))
        self.assertFalse(stale.directory.exists())

    def test_RC18_cold_reload_discovers_from_filesystem_not_live_state(self):
        session = self.write("cold", 3)
        reloaded = self.new_manager()

        candidates = reloaded.scan_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].manifest.session_id, session.session_id)


if __name__ == "__main__":
    unittest.main()
