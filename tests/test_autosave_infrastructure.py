import json
import shutil
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import MagicMock

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_models import (
    RecoveryContext,
    RecoveryManifest,
    RecoveryWorkingState,
)
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker
from core.subtitle_editing.global_undo_manager import GlobalUndoManager

try:
    from core.recovery.autosave_coordinator import AutosaveCoordinator
except (ImportError, ModuleNotFoundError):
    AutosaveCoordinator = None


class FakeScheduler:
    def __init__(self):
        self.now = 0
        self._next = 0
        self._events = {}

    def call_later(self, delay_ms, callback):
        self._next += 1
        handle = self._next
        self._events[handle] = (self.now + delay_ms, callback)
        return handle

    def cancel(self, handle):
        self._events.pop(handle, None)

    def advance(self, elapsed_ms):
        target = self.now + elapsed_ms
        while True:
            due = [
                (deadline, handle, callback)
                for handle, (deadline, callback) in self._events.items()
                if deadline <= target
            ]
            if not due:
                break
            deadline, handle, callback = min(due)
            self.now = deadline
            self._events.pop(handle, None)
            callback()
        self.now = target


class FailingStore(AtomicSnapshotStore):
    def __init__(self, failing_calls):
        self.failing_calls = set(failing_calls)
        self.calls = 0

    def write_json_atomic(self, path, payload):
        self.calls += 1
        if self.calls in self.failing_calls:
            raise OSError(f"injected failure at write {self.calls}")
        return super().write_json_atomic(path, payload)


class AutosaveCoordinatorContractTests(unittest.TestCase):
    def setUp(self):
        self.undo = GlobalUndoManager()
        self.tracker = RevisionTracker(self.undo)
        self.scheduler = FakeScheduler()
        self.active = {"session_id": "session-a", "generation": 1}
        self.writes = []
        self.logs = []

    def coordinator(self, provider=None, persist=None):
        self.assertIsNotNone(
            AutosaveCoordinator,
            "Feature 33 production contract is not implemented yet",
        )
        provider = provider or self.snapshot
        persist = persist or self.persist
        return AutosaveCoordinator(
            revision_tracker=self.tracker,
            session_provider=lambda: dict(self.active),
            snapshot_provider=provider,
            persist_snapshot=persist,
            scheduler=self.scheduler,
            activity_logger=self.logs.append,
        )

    def snapshot(self):
        return {
            "session_id": self.active["session_id"],
            "generation": self.active["generation"],
            "edit_revision": self.tracker.edit_revision,
            "segments": [{"text": "current"}],
        }

    def persist(self, state):
        self.writes.append(state)
        self.tracker.record_snapshot_success(state["edit_revision"])
        return True

    def edit(self):
        return self.tracker.record_external_change()

    def test_AS01_clean_project_does_not_autosave(self):
        coordinator = self.coordinator()
        coordinator.start()
        self.scheduler.advance(120_000)
        self.assertEqual(self.writes, [])

    def test_AS02_dirty_revision_autosaves_after_inactivity_deadline(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertEqual(len(self.writes), 1)

    def test_AS03_each_edit_restarts_only_inactivity_deadline(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(10_000)
        self.edit()
        self.scheduler.advance(29_999)
        self.assertEqual(self.writes, [])
        self.scheduler.advance(1)
        self.assertEqual(len(self.writes), 1)

    def test_AS04_continuous_edits_cannot_postpone_maximum_deadline(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        for _ in range(11):
            self.scheduler.advance(10_000)
            self.edit()
        self.assertEqual(self.scheduler.now, 110_000)
        self.assertEqual(self.writes, [])
        self.scheduler.advance(10_000)
        self.assertEqual(len(self.writes), 1)

    def test_AS05_successful_autosave_leaves_revision_tracker_dirty(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertTrue(self.tracker.is_dirty)
        self.assertEqual(self.tracker.snapshot_revision, self.tracker.edit_revision)

    def test_AS06_autosave_does_not_write_canonical_project_file(self):
        canonical_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, canonical_root, ignore_errors=True)
        canonical = canonical_root / "project.json"
        canonical.write_text('{"project":"A"}', encoding="utf-8")
        before = canonical.read_bytes()
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertEqual(canonical.read_bytes(), before)

    def test_AS07_first_success_publishes_current_recovery_pair(self):
        fixture = RecoveryFixture(self)
        fixture.write_snapshot(1)
        self.assertTrue((fixture.directory / "manifest.json").exists())
        self.assertTrue((fixture.directory / "snapshot.json").exists())

    def test_AS08_successive_snapshots_rotate_current_previous_older(self):
        fixture = RecoveryFixture(self)
        fixture.write_snapshot(1)
        fixture.write_snapshot(2)
        fixture.write_snapshot(3)
        for slot in ("current", "previous", "older"):
            self.assertTrue(fixture.pair_paths(slot)[0].exists(), slot)
            self.assertTrue(fixture.pair_paths(slot)[1].exists(), slot)

    def test_AS09_rotation_failure_preserves_readable_prior_latest_pair(self):
        for stage, call in (
            ("temp_snapshot", 1),
            ("temp_manifest", 2),
            ("previous_to_older", 3),
            ("current_to_previous", 4),
            ("before_current_publication", 5),
            ("current_snapshot_publication", 6),
            ("current_manifest_publication", 7),
        ):
            with self.subTest(stage=stage):
                fixture = RecoveryFixture(self)
                fixture.write_snapshot(1)
                old_snapshot = fixture.read_slot("current", "snapshot")
                fixture.manager.snapshot_store = FailingStore({call})
                fixture.tracker.edit_revision = 2
                fixture.tracker.is_dirty = True
                self.assertFalse(
                    fixture.manager.write_snapshot(fixture.state(2)), stage
                )
                self.assertEqual(
                    fixture.read_slot("current", "snapshot"), old_snapshot, stage
                )
                self.assertEqual(fixture.tracker.snapshot_revision, 1, stage)
                self.assertTrue(fixture.current_pair_is_valid(), stage)

    def test_AS10_snapshot_manifest_metadata_matches_durable_revision(self):
        fixture = RecoveryFixture(self)
        fixture.write_snapshot(4)
        manifest = fixture.read_slot("current", "manifest")
        snapshot = fixture.read_slot("current", "snapshot")
        self.assertEqual(manifest["snapshot_revision"], 4)
        self.assertEqual(manifest["snapshot_revision"], snapshot["edit_revision"])

    def test_AS11_stale_project_callback_cannot_persist_new_project_state(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.active.update(session_id="session-b", generation=2)
        self.scheduler.advance(30_000)
        self.assertEqual(self.writes, [])

    def test_AS12_unload_cancels_pending_autosave(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        coordinator.clear_session()
        self.scheduler.advance(120_000)
        self.assertEqual(self.writes, [])

    def test_AS13_successful_manual_save_cancels_pending_cycle(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        coordinator.manual_save_succeeded()
        self.scheduler.advance(120_000)
        self.assertEqual(self.writes, [])

    def test_AS14_failed_autosave_does_not_advance_snapshot_revision(self):
        calls = []

        def fail(_state):
            calls.append(1)
            return False

        coordinator = self.coordinator(persist=fail)
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertEqual(calls, [1])
        self.assertEqual(self.tracker.snapshot_revision, 0)
        self.assertTrue(self.tracker.is_dirty)

    def test_AS15_dispose_cancels_all_future_callbacks(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        coordinator.dispose()
        self.scheduler.advance(120_000)
        self.assertEqual(self.writes, [])

    def test_AS16_recovery_sessions_are_isolated_by_identity(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.active.update(session_id="session-b", generation=2)
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertEqual({write["session_id"] for write in self.writes}, {"session-b"})

    def test_AS17_autosave_success_and_failure_are_observable(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertTrue(self.logs)
        self.assertTrue(any("autosave" in str(entry).lower() for entry in self.logs))

    def test_AS18_read_only_activity_does_not_schedule_autosave(self):
        coordinator = self.coordinator()
        coordinator.refresh_quality_inspector()
        coordinator.filter_quality_inspector()
        coordinator.jump_to_subtitle()
        coordinator.selection_changed()
        coordinator.scrolled()
        self.scheduler.advance(120_000)
        self.assertEqual(self.writes, [])

    def test_AS19_same_revision_is_not_snapshotted_twice(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(120_000)
        coordinator.retry()
        coordinator.start()
        self.scheduler.advance(120_000)
        self.assertEqual(len(self.writes), 1)

    def test_AS20_failed_autosave_retries_after_30_seconds_without_revision_advance(self):
        attempts = []

        def fail_once(state):
            attempts.append(state["edit_revision"])
            if len(attempts) == 1:
                return False
            self.tracker.record_snapshot_success(state["edit_revision"])
            return True

        coordinator = self.coordinator(persist=fail_once)
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertEqual(self.tracker.snapshot_revision, 0)
        self.scheduler.advance(29_999)
        self.assertEqual(len(attempts), 1)
        self.scheduler.advance(1)
        self.assertEqual(attempts, [1, 1])
        self.assertEqual(self.tracker.snapshot_revision, 1)

    def test_AS21_explicit_save_clears_all_rotated_history(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.manager.record_explicit_save()
        self.assertFalse(fixture.any_slot_file_exists())

    def test_AS22_clean_point_invalidation_clears_all_rotated_history(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.manager.invalidate_snapshot_at_clean_point(1)
        self.assertFalse(fixture.any_slot_file_exists())

    def test_AS23_discard_session_removes_every_slot_and_directory(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.manager.discard_session(fixture.session.session_id)
        self.assertFalse(fixture.directory.exists())

    def test_AS24_clean_shutdown_leaves_no_rotated_orphans(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.tracker.is_dirty = False
        self.assertTrue(fixture.manager.finalize_clean_shutdown())
        self.assertFalse(fixture.directory.exists())


class PairedRecoveryContractTests(unittest.TestCase):
    def test_PAIR01_current_valid_pair_is_preferred(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 3)

    def test_PAIR02_current_invalid_falls_back_to_matching_previous_pair(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.invalidate_slot("current")
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 2)
        self.assertEqual(candidates[0].manifest.snapshot_revision, 2)

    def test_PAIR03_current_and_previous_invalid_fall_back_to_older_pair(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.invalidate_slot("current")
        fixture.invalidate_slot("previous")
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 1)

    def test_PAIR04_scanner_never_mixes_manifest_and_snapshot_slots(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        current_manifest = fixture.read_slot("current", "manifest")
        previous_snapshot = fixture.read_slot("previous", "snapshot")
        fixture.write_slot("current", "manifest", current_manifest)
        fixture.write_slot("current", "snapshot", previous_snapshot)
        candidates = fixture.manager.scan_candidates()
        self.assertTrue(
            not candidates
            or candidates[0].manifest.snapshot_revision
            == candidates[0].snapshot.edit_revision
        )

    def test_PAIR05_all_invalid_pairs_use_existing_quarantine_policy(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        for slot in ("current", "previous", "older"):
            fixture.invalidate_slot(slot)
        self.assertEqual(fixture.manager.scan_candidates(), [])
        self.assertFalse(fixture.directory.exists())
        self.assertEqual(len(list(fixture.quarantine.iterdir())), 1)

    def test_CRASH_C01_new_current_snapshot_with_old_manifest_uses_previous_pair(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.write_slot("current", "snapshot", fixture.read_slot("previous", "snapshot"))
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 2)

    def test_CRASH_C02_new_current_manifest_with_old_snapshot_uses_previous_pair(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.write_slot("current", "manifest", fixture.read_slot("previous", "manifest"))
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 2)

    def test_CRASH_C03_corrupt_current_preserves_previous_candidate(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.invalidate_slot("current")
        candidates = fixture.manager.scan_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].snapshot.edit_revision, 2)

    def test_CRASH_C04_all_slots_invalid_are_rejected(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        for slot in ("current", "previous", "older"):
            fixture.invalidate_slot(slot)
        self.assertEqual(fixture.manager.scan_candidates(), [])


class RecoveryFixture:
    def __init__(self, testcase, revision=1):
        self.testcase = testcase
        self.root = Path(tempfile.mkdtemp())
        testcase.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.sessions = self.root / "sessions"
        self.quarantine = self.root / "quarantine"
        self.sessions.mkdir()
        self.quarantine.mkdir()
        self.tracker = MagicMock(spec=RevisionTracker)
        self.tracker.is_dirty = revision > 0
        self.tracker.edit_revision = revision
        self.tracker.snapshot_revision = 0
        self.tracker.last_saved_revision = 0
        self.tracker.last_clean_revision = 0
        self.tracker.recovered_dirty_baseline = revision > 0
        self.tracker.record_snapshot_success.side_effect = lambda value: setattr(
            self.tracker, "snapshot_revision", value
        )
        self.manager = RecoveryManager(
            self.sessions,
            self.quarantine,
            self.tracker,
            AtomicSnapshotStore(),
            RecoveryValidator(),
        )
        self.session = self.manager.create_session(
            RecoveryContext(
                "project-a",
                "project-a.json",
                "video-a.mp4",
                "fp-a",
                0.0,
                session_id="session-a",
            )
        )
        self.directory = self.session.directory

    def state(self, revision):
        return RecoveryWorkingState(
            2.0,
            "session-a",
            "project-a",
            "project-a.json",
            "video-a.mp4",
            "fp-a",
            revision,
            [{"id": "seg-1", "stt": "1", "start": 0, "end": 1, "text": str(revision)}],
            {},
        )

    def manifest(self, revision):
        current = self.session.manifest
        return replace(
            current,
            edit_revision=revision,
            snapshot_revision=revision,
            last_snapshot_at=f"2026-09-18T00:00:{revision:02d}Z",
        )

    def write_snapshot(self, revision):
        self.tracker.edit_revision = revision
        self.tracker.is_dirty = True
        return self.manager.write_snapshot(self.state(revision), force=True)

    def pair_paths(self, slot):
        suffix = {"current": "", "previous": ".previous", "older": ".older"}[slot]
        return self.directory / f"manifest{suffix}.json", self.directory / f"snapshot{suffix}.json"

    def read_slot(self, slot, kind):
        manifest_path, snapshot_path = self.pair_paths(slot)
        return json.loads((manifest_path if kind == "manifest" else snapshot_path).read_text("utf-8"))

    def write_slot(self, slot, kind, payload):
        manifest_path, snapshot_path = self.pair_paths(slot)
        path = manifest_path if kind == "manifest" else snapshot_path
        path.write_text(json.dumps(payload), encoding="utf-8")

    def seed_all_slots(self):
        self.write_snapshot(1)
        self.write_slot("previous", "manifest", asdict(self.manifest(2)))
        self.write_slot("previous", "snapshot", asdict(self.state(2)))
        self.write_slot("older", "manifest", asdict(self.manifest(1)))
        self.write_slot("older", "snapshot", asdict(self.state(1)))
        self.write_slot("current", "manifest", asdict(self.manifest(3)))
        self.write_slot("current", "snapshot", asdict(self.state(3)))

    def invalidate_slot(self, slot):
        manifest_path, _ = self.pair_paths(slot)
        manifest_path.write_text("{bad", encoding="utf-8")

    def current_pair_is_valid(self):
        manifest_path, snapshot_path = self.pair_paths("current")
        manifest = RecoveryManifest(**json.loads(manifest_path.read_text("utf-8")))
        snapshot = RecoveryWorkingState(**json.loads(snapshot_path.read_text("utf-8")))
        return RecoveryValidator().validate_data(manifest, snapshot).is_valid

    def any_slot_file_exists(self):
        return any(path.exists() for slot in ("current", "previous", "older") for path in self.pair_paths(slot))


if __name__ == "__main__":
    unittest.main()
