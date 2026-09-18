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


SEMANTIC_FAILURE_STAGES = (
    "temp_snapshot",
    "temp_manifest",
    "previous_to_older",
    "current_to_previous",
    "before_current_publication",
    "current_snapshot_publication",
    "current_manifest_publication",
)


class SemanticFailureStore(AtomicSnapshotStore):
    """Contract seam for semantic failure injection, independent of write count."""

    def __init__(self, failure_stage):
        self.failure_stage = failure_stage
        self.observed_stages = []

    def before_stage(self, stage):
        self.observed_stages.append(stage)
        if stage == self.failure_stage:
            raise OSError(f"injected failure at semantic stage {stage}")


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
        fixture.assert_pair_revision("current", 3)
        fixture.assert_pair_revision("previous", 2)
        fixture.assert_pair_revision("older", 1)
        fixture.write_snapshot(4)
        fixture.assert_pair_revision("current", 4)
        fixture.assert_pair_revision("previous", 3)
        fixture.assert_pair_revision("older", 2)

    def test_AS09_rotation_failure_preserves_readable_prior_latest_pair(self):
        for stage in SEMANTIC_FAILURE_STAGES:
            with self.subTest(stage=stage):
                fixture = RecoveryFixture(self)
                fixture.write_snapshot(1)
                canonical_before = fixture.canonical.read_bytes()
                failure_store = SemanticFailureStore(stage)
                fixture.manager.snapshot_store = failure_store
                fixture.tracker.edit_revision = 2
                fixture.tracker.is_dirty = True
                self.assertFalse(
                    fixture.manager.write_snapshot(fixture.state(2)), stage
                )
                self.assertIn(stage, failure_store.observed_stages, stage)
                self.assertEqual(fixture.tracker.snapshot_revision, 1, stage)
                self.assertEqual(fixture.canonical.read_bytes(), canonical_before, stage)
                self.assertTrue(fixture.valid_slots_with_revision(1), stage)
                candidates = (
                    fixture.manager.scan_candidates()
                    if fixture.directory.exists()
                    else []
                )
                self.assertTrue(
                    any(candidate.snapshot.edit_revision == 1 for candidate in candidates),
                    stage,
                )

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

    def test_AS11B_post_capture_identity_change_blocks_persist(self):
        def capture_then_switch():
            state = self.snapshot()
            self.active.update(session_id="session-b", generation=2)
            return state

        coordinator = self.coordinator(provider=capture_then_switch)
        self.edit()
        coordinator.start()
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

    def test_AS17_successful_autosave_is_observable(self):
        coordinator = self.coordinator()
        self.edit()
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertTrue(self.logs)
        self.assertTrue(any("autosave" in str(entry).lower() for entry in self.logs))

    def test_AS17_failure_is_observable_without_changing_editing_state(self):
        def fail(_state):
            return False

        coordinator = self.coordinator(persist=fail)
        self.edit()
        revision_before = self.tracker.edit_revision
        coordinator.start()
        self.scheduler.advance(30_000)
        self.assertTrue(self.logs)
        self.assertEqual(self.tracker.edit_revision, revision_before)
        self.assertTrue(self.tracker.is_dirty)

    def test_AS17_lifecycle_events_do_not_pollute_activity_stream(self):
        coordinator = self.coordinator()

        coordinator.start()
        coordinator.bind_session("session-b")
        coordinator.clear_session()
        coordinator.manual_save_succeeded()

        self.assertEqual(self.logs, [])

    def test_AS18_read_only_activity_does_not_schedule_autosave(self):
        coordinator = self.coordinator()
        coordinator.start()
        revision_before = self.tracker.edit_revision
        self.scheduler.advance(120_000)
        self.assertEqual(self.tracker.edit_revision, revision_before)
        self.assertEqual(self.writes, [])

    def test_AS19_same_revision_is_not_snapshotted_twice(self):
        coordinator = self.coordinator()
        self.edit()
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
        self.assertTrue((fixture.directory / "active.lock").exists())
        self.assertTrue((fixture.directory / "manifest.json").exists())
        self.assertFalse(fixture.history_file_exists())

    def test_AS22_clean_point_invalidation_clears_all_rotated_history(self):
        fixture = RecoveryFixture(self)
        fixture.seed_all_slots()
        fixture.manager.invalidate_snapshot_at_clean_point(3)
        self.assertTrue((fixture.directory / "active.lock").exists())
        self.assertTrue((fixture.directory / "manifest.json").exists())
        self.assertFalse(fixture.history_file_exists())

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
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].manifest.snapshot_revision, 2)
        self.assertEqual(candidates[0].snapshot.edit_revision, 2)

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

    def test_AS26_manifest_only_session_is_not_quarantined(self):
        fixture = RecoveryFixture(self)

        self.assertEqual(fixture.manager.scan_candidates(), [])
        self.assertTrue(fixture.directory.exists())
        self.assertEqual(list(fixture.quarantine.iterdir()), [])

        fixture.tracker.edit_revision = 1
        fixture.tracker.is_dirty = True
        self.assertTrue(fixture.manager.write_snapshot(fixture.state(1)))
        fixture.manager.record_explicit_save()

        self.assertEqual(fixture.manager.scan_candidates(), [])
        self.assertTrue(fixture.directory.exists())
        self.assertEqual(list(fixture.quarantine.iterdir()), [])

    def test_AS27_discard_removes_recovery_temp_artifacts(self):
        fixture = RecoveryFixture(self)
        for name in (
            "manifest.tmp",
            "snapshot.tmp",
            "manifest.previous.tmp",
            "snapshot.previous.tmp",
            "manifest.older.tmp",
            "snapshot.older.tmp",
        ):
            (fixture.directory / name).write_text("stale", encoding="utf-8")

        fixture.manager.discard_session(fixture.session.session_id)

        self.assertFalse(fixture.directory.exists())


class RecoveryFixture:
    def __init__(self, testcase, revision=1):
        self.testcase = testcase
        self.root = Path(tempfile.mkdtemp())
        testcase.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.sessions = self.root / "sessions"
        self.quarantine = self.root / "quarantine"
        self.sessions.mkdir()
        self.quarantine.mkdir()
        self.canonical = self.root / "canonical-project.json"
        self.canonical.write_text('{"project":"A"}', encoding="utf-8")
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
                str(self.canonical),
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
            str(self.canonical),
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
        result = self.manager.write_snapshot(self.state(revision), force=True)
        self.session = self.manager._active_session
        return result

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
        self.write_snapshot(2)
        self.write_snapshot(3)
        self.write_slot("previous", "manifest", asdict(self.manifest(2)))
        self.write_slot("previous", "snapshot", asdict(self.state(2)))
        self.write_slot("older", "manifest", asdict(self.manifest(1)))
        self.write_slot("older", "snapshot", asdict(self.state(1)))

    def invalidate_slot(self, slot):
        manifest_path, _ = self.pair_paths(slot)
        manifest_path.write_text("{bad", encoding="utf-8")

    def assert_pair_revision(self, slot, revision):
        manifest_path, snapshot_path = self.pair_paths(slot)
        self.testcase.assertTrue(manifest_path.exists(), slot)
        self.testcase.assertTrue(snapshot_path.exists(), slot)
        manifest = RecoveryManifest(**json.loads(manifest_path.read_text("utf-8")))
        snapshot = RecoveryWorkingState(**json.loads(snapshot_path.read_text("utf-8")))
        result = RecoveryValidator().validate_data(manifest, snapshot)
        self.testcase.assertTrue(result.is_valid, slot)
        self.testcase.assertEqual(manifest.snapshot_revision, revision, slot)
        self.testcase.assertEqual(snapshot.edit_revision, revision, slot)

    def valid_slots_with_revision(self, revision):
        valid = []
        for slot in ("current", "previous", "older"):
            manifest_path, snapshot_path = self.pair_paths(slot)
            if not manifest_path.exists() or not snapshot_path.exists():
                continue
            try:
                manifest = RecoveryManifest(
                    **json.loads(manifest_path.read_text("utf-8"))
                )
                snapshot = RecoveryWorkingState(
                    **json.loads(snapshot_path.read_text("utf-8"))
                )
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            result = RecoveryValidator().validate_data(manifest, snapshot)
            if result.is_valid and snapshot.edit_revision == revision:
                valid.append(slot)
        return valid

    def history_file_exists(self):
        return any(
            path.exists()
            for path in (
                self.directory / "snapshot.json",
                self.directory / "manifest.previous.json",
                self.directory / "snapshot.previous.json",
                self.directory / "manifest.older.json",
                self.directory / "snapshot.older.json",
            )
        )

if __name__ == "__main__":
    unittest.main()
