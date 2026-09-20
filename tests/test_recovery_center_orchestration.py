import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.recovery.recovery_models import (
    RecoveryCandidate,
    RecoveryEntry,
    RecoveryManifest,
    RecoveryWorkingState,
)


class _CanonicalSave:
    enabled = True

    def __init__(self, events, result=True):
        self.events = events
        self.result = result

    def flush_now(self):
        self.events.append("flush-a")
        return self.result


class _ProjectService:
    def __init__(self, events, target, *, open_result=True, clear_on_failure=False):
        self.events = events
        self.target = target
        self.open_result = open_result
        self.clear_on_failure = clear_on_failure
        self.current_project = SimpleNamespace(project_id="project-a")
        self.project_dir = "D:/project-a.ai-subtitle"

    def open_project(self, project_root):
        self.events.append(f"open:{project_root}")
        if not self.open_result:
            if self.clear_on_failure:
                self.current_project = None
                self.project_dir = None
            raise OSError("target open failed")
        self.current_project = self.target
        self.project_dir = "D:/project-b.ai-subtitle"
        return self.target

    def close_project(self):
        self.events.append("close")
        self.current_project = None
        self.project_dir = None


class _RecoveryManager:
    def __init__(self, events, entry, state, *, live_session_id=None):
        self.events = events
        self.entry = entry
        self.state = state
        self.live_session_id = live_session_id
        self.handoff_called = False
        self.session_exists = True

    def resolve_recovery_entry(self, session_id, **_kwargs):
        self.events.append(f"resolve:{session_id}")
        if not self.session_exists or session_id != self.entry.session_id:
            return None
        return self.entry

    def resolve_recovery_candidate(self, session_id, **_kwargs):
        self.events.append(f"candidate:{session_id}")
        if not self.session_exists or session_id != self.entry.session_id:
            return None
        manifest = RecoveryManifest(
            schema_version=1,
            session_id=self.entry.session_id,
            app_version="test",
            project_id=self.entry.project_id,
            project_file_path=self.entry.project_root,
            video_path=self.entry.video_path,
            source_fingerprint=self.state.source_fingerprint,
            source_modified_at=0.0,
            created_at=self.entry.created_at,
            last_snapshot_at=self.entry.effective_snapshot_timestamp,
            edit_revision=self.entry.snapshot_revision,
            snapshot_revision=self.entry.snapshot_revision,
            last_saved_revision=self.entry.last_saved_revision,
            last_clean_revision=self.entry.last_clean_revision,
        )
        return RecoveryCandidate(manifest, self.state)

    def validate_candidate(self, _candidate, actual_source_info=None):
        if self.entry.source_status == "AVAILABLE":
            return SimpleNamespace(is_valid=True, source_matches=True, source_reason="")
        return SimpleNamespace(
            is_valid=True,
            source_matches=False,
            source_reason=self.entry.source_status,
        )

    def handoff_recovered_state(self, *_args, **_kwargs):
        self.events.append("handoff")
        self.handoff_called = True


class RecoveryCenterOrchestrationContract(unittest.TestCase):
    def setUp(self):
        from ui.Gui import MainWindow

        self.MainWindow = MainWindow
        self.events = []
        self.target_project = SimpleNamespace(project_id="project-b")
        self.entry = RecoveryEntry(
            session_id="recovery-b",
            project_id="project-b",
            project_root="D:/project-b.ai-subtitle",
            video_path="D:/shared.mp4",
            effective_snapshot_timestamp="2026-09-21T00:00:02+00:00",
            created_at="2026-09-21T00:00:01+00:00",
            snapshot_revision=7,
            last_saved_revision=3,
            last_clean_revision=3,
            source_status="AVAILABLE",
            unlinked_restore_allowed=False,
            linked_restore_allowed=True,
        )
        self.state = RecoveryWorkingState(
            schema_version=2.0,
            session_id="recovery-b",
            project_id="project-b",
            project_file_path="D:/project-b.ai-subtitle",
            video_path="D:/shared.mp4",
            source_fingerprint="fp-b",
            edit_revision=7,
            segments=[{"id": "b-1", "stt": "1", "text": "Recovered B"}],
            workspace_state={"active_page": "editor"},
        )

    def window(self, *, flush_result=True, open_result=True, clear_on_failure=False):
        window = self.MainWindow.__new__(self.MainWindow)
        window.project_service = _ProjectService(
            self.events,
            self.target_project,
            open_result=open_result,
            clear_on_failure=clear_on_failure,
        )
        window.canonical_save_coordinator = _CanonicalSave(
            self.events, result=flush_result
        )
        window.recovery_manager = _RecoveryManager(
            self.events, self.entry, self.state
        )
        window.autosave_coordinator = SimpleNamespace()
        window.revision_tracker = SimpleNamespace(
            edit_revision=7,
            snapshot_revision=7,
            recovered_dirty_baseline=False,
            is_dirty=False,
        )
        def restore_from_snapshot(snapshot_revision, last_saved_revision, last_clean_revision):
            window.revision_tracker.edit_revision = snapshot_revision
            window.revision_tracker.snapshot_revision = snapshot_revision
            window.revision_tracker.recovered_dirty_baseline = True
            window.revision_tracker.is_dirty = True

        window.revision_tracker.restore_from_snapshot = MagicMock(
            side_effect=restore_from_snapshot
        )
        window.apply_recovery_working_state = MagicMock(
            side_effect=lambda state, linked: self.events.append(
                f"apply:{state.project_id}:{linked}"
            )
        )
        return window

    def test_C2_01_restore_resolves_by_session_id(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertIn("candidate:recovery-b", self.events)
        self.assertNotIn("candidate:D:/shared.mp4", self.events)

    def test_C2_02_flushes_active_project_before_opening_target(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertLess(self.events.index("flush-a"), self.events.index("open:D:/project-b.ai-subtitle"))

    def test_C2_03_flush_failure_blocks_restore_and_preserves_source(self):
        window = self.window(flush_result=False)

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(window.project_service.current_project.project_id, "project-a")
        self.assertNotIn("open:D:/project-b.ai-subtitle", self.events)
        self.assertNotIn("apply:project-b:True", self.events)
        self.assertFalse(window.recovery_manager.handoff_called)

    def test_C2_04_linked_restore_opens_target_and_applies_recovered_state(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(window.project_service.current_project.project_id, "project-b")
        self.assertIn("apply:project-b:True", self.events)

    def test_C2_05_successful_restore_keeps_recovered_baseline_dirty(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertTrue(window.revision_tracker.recovered_dirty_baseline)
        self.assertTrue(window.revision_tracker.is_dirty)
        self.assertEqual(window.revision_tracker.edit_revision, 7)
        self.assertEqual(window.revision_tracker.snapshot_revision, 7)

    def test_C2_06_restore_does_not_trigger_canonical_save_for_recovered_baseline(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(self.events.count("flush-a"), 1)

    def test_C2_07_source_missing_requires_unlinked_mode(self):
        window = self.window()
        window.recovery_manager.entry = replace(
            self.entry,
            source_status="SOURCE_MISSING",
            linked_restore_allowed=False,
            unlinked_restore_allowed=True,
        )

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))
        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=False))
        self.assertNotIn("open:D:/project-b.ai-subtitle", self.events)
        self.assertIn("close", self.events)
        self.assertIn("apply:project-b:False", self.events)
        self.assertIsNone(window.project_service.current_project)

    def test_C2_08_source_mismatch_requires_unlinked_mode(self):
        window = self.window()
        window.recovery_manager.entry = replace(
            self.entry,
            source_status="SOURCE_MISMATCH",
            linked_restore_allowed=False,
            unlinked_restore_allowed=True,
        )

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))
        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=False))
        self.assertNotIn("open:D:/project-b.ai-subtitle", self.events)
        self.assertIn("close", self.events)
        self.assertIn("apply:project-b:False", self.events)
        self.assertIsNone(window.project_service.current_project)

    def test_C2_09_target_open_failure_does_not_apply_or_handoff(self):
        window = self.window(open_result=False)

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(window.project_service.current_project.project_id, "project-a")
        self.assertNotIn("apply:project-b:True", self.events)
        self.assertFalse(window.recovery_manager.handoff_called)
        self.assertTrue(window.recovery_manager.session_exists)

    def test_C2_09_target_open_failure_with_no_project_stays_no_project(self):
        window = self.window(open_result=False, clear_on_failure=True)

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertIsNone(window.project_service.current_project)
        self.assertNotIn("apply:project-b:True", self.events)
        self.assertFalse(window.recovery_manager.handoff_called)
        self.assertTrue(window.recovery_manager.session_exists)

    def test_C2_10_handoff_occurs_only_after_target_apply_succeeds(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertLess(self.events.index("apply:project-b:True"), self.events.index("handoff"))

    def test_C2_11_apply_failure_does_not_report_success_or_handoff(self):
        window = self.window()
        window.apply_recovery_working_state.side_effect = RuntimeError("apply failed")

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertFalse(window.recovery_manager.handoff_called)
        self.assertTrue(window.recovery_manager.session_exists)
        self.assertIsNone(window.project_service.current_project)
        self.assertIn("close", self.events)

    def test_C2_12_same_video_restores_project_identity_b(self):
        window = self.window()

        self.assertTrue(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(window.project_service.current_project.project_id, "project-b")
        self.assertEqual(window.project_service.project_dir, "D:/project-b.ai-subtitle")

    def test_C2_13_stale_entry_fails_without_mutating_active_project(self):
        window = self.window()
        window.recovery_manager.session_exists = False

        self.assertFalse(window._restore_recovery_entry("recovery-b", linked=True))

        self.assertEqual(window.project_service.current_project.project_id, "project-a")
        self.assertEqual(self.events, ["candidate:recovery-b"])

    def test_C2_14_active_live_entry_is_refused(self):
        window = self.window()
        window.recovery_manager.live_session_id = "recovery-b"

        self.assertFalse(
            window._restore_recovery_entry(
                "recovery-b", linked=True, active_session_id="recovery-b"
            )
        )

        self.assertEqual(window.project_service.current_project.project_id, "project-a")
        self.assertFalse(window.recovery_manager.handoff_called)


if __name__ == "__main__":
    unittest.main()
