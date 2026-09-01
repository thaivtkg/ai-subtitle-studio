# Sprint 11 — Project Reliability & Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single-instance runtime protection, monotonic revision tracking, atomic crash-recovery snapshots, recovery handoff, source guarding, and safe close/save semantics without allowing recovery or export operations to silently overwrite canonical project state.

**Architecture:** `GlobalUndoManager` continues to own command history, while a new `RevisionTracker` becomes the source of truth for edit/snapshot/save/clean revisions and recovered-dirty state. A UI-free `RecoveryManager` owns session lifecycle and delegates durable writes to `AtomicSnapshotStore` and candidate validation to `RecoveryValidator`; `main.py` owns single-instance/bootstrap ordering through `SingleInstanceGuard` before heavy UI/AI services start.

**Tech Stack:** Python 3.10+, PySide6 (`QObject`, `Signal`, `QTimer`, `QLocalServer`, `QLocalSocket`, `QUndoStack`), stdlib `json`, `uuid`, `pathlib`, `os.replace`, `os.fsync`, `shutil`, `dataclasses`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-01-sprint-11-project-reliability-recovery-design.md`

## Global Constraints

- Recovery data lives only under `%LOCALAPPDATA%/AI Subtitle Studio/recovery/` through `RuntimePaths`.
- Recovery is session-scoped: `sessions/<session_id>/{manifest.json,snapshot.json,active.lock}`.
- `snapshot.json` is written through temp-file + flush/fsync + `os.replace`; never update it in-place.
- Exactly one application instance may own heavy UI/AI/media runtime resources.
- IPC accepts only `ACTIVATE_WINDOW`, `OPEN_PROJECT`, and `OPEN_MEDIA`.
- `RevisionTracker` is the source of truth for dirty state used by recovery scheduling, title state, and close guards.
- `edit_revision` is monotonic and increments exactly once per successful canonical state transition.
- Recovery never serializes `QUndoStack`/`QUndoCommand` history.
- Recovery restore changes working RAM state only; it does not overwrite canonical project/Draft/SRT files.
- Export SRT/VTT/TXT and hardsub/video export never update `last_saved_revision` and never call `mark_saved()`.
- A recovered baseline remains dirty until explicit canonical Save or explicit Discard.
- Old recovery Session A is deleted only after recovered state is durably snapshotted into Session B.
- All existing Sprint 10 tests must remain green.

---

## File Map

### New recovery subsystem

- `core/recovery/__init__.py` — package marker and public exports only.
- `core/recovery/recovery_models.py` — immutable/serializable dataclasses for session context, manifest, working state, candidates, validation results.
- `core/recovery/revision_tracker.py` — monotonic revisions and dirty-state source of truth.
- `core/recovery/atomic_snapshot_store.py` — atomic JSON persistence only.
- `core/recovery/recovery_validator.py` — schema, revision, and source-guard validation only.
- `core/recovery/recovery_manager.py` — session lifecycle, candidate scan, autosave decision, cleanup, quarantine, handoff.

### Runtime/bootstrap

- `core/runtime/runtime_paths.py` — add recovery directory getters.
- `core/runtime/single_instance_guard.py` — `QLocalServer`/`QLocalSocket` ownership and whitelisted IPC.
- `core/project/source_fingerprint.py` — shared media fingerprint helper extracted from `ProjectService`.
- `main.py` — single-instance acquisition, recovery pre-scan, recovery bootstrap decision before showing `MainWindow`.

### UI integration

- `ui/dialogs/recovery_dialog.py` — normal recovery prompt.
- `ui/dialogs/source_mismatch_dialog.py` — linked-restore blocked UI.
- `ui/Gui.py` — dependency wiring, canonical working-state capture/apply, title dirty marker, close guard, canonical Save semantics, IPC routing.
- `core/services/workspace_service.py` — reuse/extend canonical workspace capture/apply without adding a second workspace model.
- `core/services/project_service.py` — use shared source fingerprint helper; return/save success deterministically where needed by caller.

### Tests

- `tests/test_recovery_foundation.py`
- `tests/test_revision_tracker.py`
- `tests/test_recovery_atomicity.py`
- `tests/test_recovery_manager.py`
- `tests/test_single_instance_guard.py`
- `tests/test_recovery_ui_integration.py`
- `tests/test_recovery_end_to_end.py`

---

### Task 1: Recovery Paths and Shared Source Fingerprint

**Files:**
- Create: `core/project/source_fingerprint.py`
- Modify: `core/runtime/runtime_paths.py`
- Modify: `core/services/project_service.py`
- Create: `tests/test_recovery_foundation.py`

**Interfaces:**
- Produces: `generate_source_info(video_path: str) -> SourceInfo`
- Produces: `RuntimePaths.get_recovery_dir() -> Path`
- Produces: `RuntimePaths.get_recovery_sessions_dir() -> Path`
- Produces: `RuntimePaths.get_recovery_quarantine_dir() -> Path`
- Consumers: Tasks 4, 5, 7, and 8.

- [ ] **Step 1: Write failing path tests**

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime.runtime_paths import RuntimePaths


class TestRecoveryPaths(unittest.TestCase):
    def test_recovery_paths_live_under_user_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                root = RuntimePaths.get_user_data_dir()
                self.assertEqual(RuntimePaths.get_recovery_dir(), root / "recovery")
                self.assertEqual(
                    RuntimePaths.get_recovery_sessions_dir(),
                    root / "recovery" / "sessions",
                )
                self.assertEqual(
                    RuntimePaths.get_recovery_quarantine_dir(),
                    root / "recovery" / "quarantine",
                )

    def test_ensure_user_data_dirs_creates_recovery_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                RuntimePaths.ensure_user_data_dirs()
                self.assertTrue(RuntimePaths.get_recovery_sessions_dir().is_dir())
                self.assertTrue(RuntimePaths.get_recovery_quarantine_dir().is_dir())
```

- [ ] **Step 2: Run the recovery-path tests and confirm RED**

Run:

```bash
python -m unittest discover -s tests -p "test_recovery_foundation.py" -v
```

Expected: FAIL because the recovery path getters do not exist.

- [ ] **Step 3: Add the recovery path getters and directory creation**

Add to `RuntimePaths`:

```python
@staticmethod
def get_recovery_dir() -> Path:
    return RuntimePaths.get_user_data_dir() / "recovery"

@staticmethod
def get_recovery_sessions_dir() -> Path:
    return RuntimePaths.get_recovery_dir() / "sessions"

@staticmethod
def get_recovery_quarantine_dir() -> Path:
    return RuntimePaths.get_recovery_dir() / "quarantine"
```

Extend `ensure_user_data_dirs()` with:

```python
cls.get_recovery_dir().mkdir(exist_ok=True)
cls.get_recovery_sessions_dir().mkdir(exist_ok=True)
cls.get_recovery_quarantine_dir().mkdir(exist_ok=True)
```

- [ ] **Step 4: Write failing shared-fingerprint regression test**

Append to `tests/test_recovery_foundation.py`:

```python
import os

from core.project.source_fingerprint import generate_source_info


class TestSourceFingerprint(unittest.TestCase):
    def test_shared_fingerprint_matches_project_source_shape(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"subtitle-source" * 64)
            path = handle.name
        try:
            info = generate_source_info(path)
            self.assertEqual(info.path, path)
            self.assertEqual(info.filename, os.path.basename(path))
            self.assertGreater(info.size_bytes, 0)
            self.assertEqual(len(info.fingerprint), 64)
        finally:
            os.remove(path)
```

- [ ] **Step 5: Run the test and confirm RED**

Run the same unittest discovery command.

Expected: import failure for `core.project.source_fingerprint`.

- [ ] **Step 6: Extract the fingerprint implementation**

Create `core/project/source_fingerprint.py` with one public function that preserves the existing Sprint 10 algorithm: hash the file size string, first 1 MiB, and final 1 MiB when applicable, then return `SourceInfo`.

Use this exact public signature:

```python
def generate_source_info(video_path: str) -> SourceInfo:
    """Return canonical SourceInfo using the application's fast SHA-256 fingerprint."""
```

Modify `ProjectService._generate_fingerprint()` to delegate directly:

```python
def _generate_fingerprint(self, video_path: str) -> SourceInfo:
    return generate_source_info(video_path)
```

- [ ] **Step 7: Run foundation tests GREEN**

```bash
python -m unittest discover -s tests -p "test_recovery_foundation.py" -v
```

Expected: PASS.

- [ ] **Step 8: Run existing project/generation regression tests**

```bash
python -m unittest discover -s tests -p "test_subtitle_generation.py" -v
python -m unittest discover -s tests -p "test_video_metadata.py" -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/project/source_fingerprint.py core/runtime/runtime_paths.py core/services/project_service.py tests/test_recovery_foundation.py
git commit -m "feat: add recovery paths and shared source fingerprint"
```

---

### Task 2: Recovery Models and Schema Validator

**Files:**
- Create: `core/recovery/__init__.py`
- Create: `core/recovery/recovery_models.py`
- Create: `core/recovery/recovery_validator.py`
- Modify: `tests/test_recovery_foundation.py`

**Interfaces:**
- Produces: `RecoveryContext`, `RecoveryManifest`, `RecoveryWorkingState`, `RecoveryCandidate`, `RecoveryValidationResult`.
- Produces: `RecoveryValidator.validate_candidate(candidate) -> RecoveryValidationResult`.
- Consumes: `generate_source_info()` from Task 1.
- Consumers: Tasks 4, 5, 7, 8.

- [ ] **Step 1: Define failing model/validator tests**

Append tests that construct a manifest/snapshot pair and assert:

```python
from core.recovery.recovery_models import (
    RecoveryCandidate,
    RecoveryManifest,
    RecoveryWorkingState,
)
from core.recovery.recovery_validator import RecoveryValidator


def make_manifest() -> RecoveryManifest:
    return RecoveryManifest(
        schema_version=1,
        session_id="session-a",
        app_version="test",
        project_id="project-1",
        project_file_path="C:/project",
        video_path="C:/video.mp4",
        source_fingerprint="abc",
        source_modified_at=1.0,
        created_at="2026-09-01T00:00:00",
        last_snapshot_at="2026-09-01T00:00:30",
        edit_revision=5,
        snapshot_revision=5,
        last_saved_revision=2,
        last_clean_revision=2,
    )


def make_snapshot() -> RecoveryWorkingState:
    return RecoveryWorkingState(
        schema_version=2.0,
        session_id="session-a",
        project_id="project-1",
        project_file_path="C:/project",
        video_path="C:/video.mp4",
        source_fingerprint="abc",
        edit_revision=5,
        segments=[{
            "id": "seg-1",
            "stt": "1",
            "start": 1000,
            "end": 2000,
            "text": "hello",
            "status": "draft",
            "metadata": {"type": "normal"},
        }],
        workspace_state={
            "active_page": "editor",
            "active_tab": "inline_editor",
            "selected_segment_id": "seg-1",
            "playback_position_ms": 1200,
            "subtitle_preview_enabled": True,
            "splitter_sizes": [400, 200],
        },
    )


class TestRecoveryValidator(unittest.TestCase):
    def test_revision_mismatch_is_invalid(self):
        manifest = make_manifest()
        snapshot = make_snapshot()
        snapshot.edit_revision = 4
        result = RecoveryValidator().validate_data(manifest, snapshot)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "SNAPSHOT_REVISION_MISMATCH")

    def test_missing_segment_uuid_is_invalid(self):
        manifest = make_manifest()
        snapshot = make_snapshot()
        snapshot.segments[0]["id"] = ""
        result = RecoveryValidator().validate_data(manifest, snapshot)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "INVALID_SEGMENT_SCHEMA")
```

- [ ] **Step 2: Run tests RED**

```bash
python -m unittest discover -s tests -p "test_recovery_foundation.py" -v
```

Expected: missing recovery models/validator imports.

- [ ] **Step 3: Implement dataclasses with explicit serialization boundaries**

Create dataclasses whose field names exactly match the Locked Spec. Include `to_dict()` / `from_dict()` methods so JSON conversion never depends on UI objects.

`RecoveryValidationResult` must contain:

```python
@dataclass(frozen=True)
class RecoveryValidationResult:
    is_valid: bool
    reason: str = ""
    source_matches: bool = True
    source_reason: str = ""
```

- [ ] **Step 4: Implement pure schema/revision validation**

`RecoveryValidator.validate_data()` must check, in order:

```text
manifest schema == 1
snapshot schema == 2.0
session IDs match
all revision values are non-negative integers
manifest.snapshot_revision == snapshot.edit_revision
manifest.snapshot_revision <= manifest.edit_revision
segment required keys exist
segment id is non-empty
segment stt is non-empty
start/end are numeric or canonical timestamp-compatible values
workspace_state is a mapping
```

Return deterministic reason constants such as:

```text
UNSUPPORTED_MANIFEST_SCHEMA
UNSUPPORTED_SNAPSHOT_SCHEMA
SESSION_ID_MISMATCH
INVALID_REVISION
SNAPSHOT_REVISION_MISMATCH
INVALID_SEGMENT_SCHEMA
INVALID_WORKSPACE_SCHEMA
```

- [ ] **Step 5: Add source-guard API without coupling it to filesystem discovery**

Use this signature:

```python
def validate_source(
    self,
    manifest: RecoveryManifest,
    actual_source_info: SourceInfo | None,
) -> RecoveryValidationResult:
```

Rules:

```text
actual_source_info is None → valid snapshot data, source_matches=False, source_reason="SOURCE_MISSING"
fingerprint differs       → valid snapshot data, source_matches=False, source_reason="SOURCE_MISMATCH"
fingerprint matches       → source_matches=True
```

Source mismatch blocks linked restoration but does not classify otherwise-valid recovery JSON as corrupt.

- [ ] **Step 6: Run foundation tests GREEN**

```bash
python -m unittest discover -s tests -p "test_recovery_foundation.py" -v
```

- [ ] **Step 7: Commit**

```bash
git add core/recovery tests/test_recovery_foundation.py
git commit -m "feat: define recovery models and validation"
```

---

### Task 3: RevisionTracker and Undo-to-Clean Semantics

**Files:**
- Create: `core/recovery/revision_tracker.py`
- Modify: `core/subtitle_editing/global_undo_manager.py`
- Create: `tests/test_revision_tracker.py`

**Interfaces:**
- Consumes: `GlobalUndoManager.state_changed`, `GlobalUndoManager.undo_stack.isClean()`.
- Produces: `RevisionTracker.record_state_transition()`, `record_snapshot_success()`, `record_explicit_save_success()`, `restore_from_snapshot()`, `reset_for_new_document()`.
- Produces signals: `dirty_changed(bool)`, `revision_changed(int)`, `clean_point_reached(int)`.
- Consumers: RecoveryManager and MainWindow tasks.

- [ ] **Step 1: Write TC85, TC87 and TC88 as failing tests**

```python
import unittest

from core.recovery.revision_tracker import RevisionTracker
from core.subtitle_editing.commands.edit_text_command import EditTextCommand
from core.subtitle_editing.global_undo_manager import GlobalUndoManager


class TestRevisionTracker(unittest.TestCase):
    def setUp(self):
        self.data = [{"id": "a", "stt": "1", "start": 0, "end": 1000, "text": "A"}]
        self.undo = GlobalUndoManager()
        self.tracker = RevisionTracker(self.undo)

    def test_tc85_push_undo_redo_are_monotonic_once_each(self):
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.assertEqual(self.tracker.edit_revision, 1)
        self.undo.undo()
        self.assertEqual(self.tracker.edit_revision, 2)
        self.undo.redo()
        self.assertEqual(self.tracker.edit_revision, 3)

    def test_tc87_clean_changed_does_not_double_increment(self):
        self.undo.push(EditTextCommand(0, "A", "B", self.data))
        self.tracker.record_explicit_save_success()
        self.undo.push(EditTextCommand(0, "B", "C", self.data))
        before = self.tracker.edit_revision
        self.undo.undo()
        self.assertEqual(self.tracker.edit_revision, before + 1)

    def test_tc88_recovered_empty_stack_is_still_dirty(self):
        self.tracker.restore_from_snapshot(10, 4, 4)
        self.assertTrue(self.undo.undo_stack.isClean())
        self.assertTrue(self.tracker.is_dirty)
        self.assertEqual(self.tracker.edit_revision, 10)
```

- [ ] **Step 2: Run tests RED**

```bash
python -m unittest discover -s tests -p "test_revision_tracker.py" -v
```

Expected: missing `RevisionTracker`.

- [ ] **Step 3: Implement RevisionTracker and connect exactly one transition path**

Connect once in `__init__`:

```python
undo_manager.state_changed.connect(self.record_state_transition)
```

`record_state_transition()` performs:

```text
old_dirty = is_dirty
edit_revision += 1
emit revision_changed(edit_revision)
if undo stack is clean AND recovered_dirty_baseline is False:
    last_clean_revision = edit_revision
    emit clean_point_reached(edit_revision)
emit dirty_changed only when dirty value changed
```

Do **not** increment revision from `clean_changed`.

- [ ] **Step 4: Write TC86 and TC89**

```python
def test_tc86_undo_to_saved_point_records_clean_revision(self):
    self.undo.push(EditTextCommand(0, "A", "B", self.data))
    self.tracker.record_explicit_save_success()
    saved_revision = self.tracker.last_saved_revision
    self.undo.push(EditTextCommand(0, "B", "C", self.data))
    self.undo.undo()
    self.assertGreater(self.tracker.last_clean_revision, saved_revision)
    self.assertFalse(self.tracker.is_dirty)


def test_tc89_undo_to_recovered_baseline_stays_dirty(self):
    self.tracker.restore_from_snapshot(10, 4, 4)
    self.undo.push(EditTextCommand(0, "A", "B", self.data))
    self.undo.undo()
    self.assertTrue(self.tracker.recovered_dirty_baseline)
    self.assertTrue(self.tracker.is_dirty)
    self.assertEqual(self.tracker.last_clean_revision, 4)
```

- [ ] **Step 5: Run tracker tests GREEN**

```bash
python -m unittest discover -s tests -p "test_revision_tracker.py" -v
```

- [ ] **Step 6: Run Sprint 10 undo/editor regressions**

```bash
python -m unittest discover -s tests -p "test_subtitle_edit_commands.py" -v
python -m unittest discover -s tests -p "test_sprint10_integration.py" -v
python -m unittest discover -s tests -p "test_timeline.py" -v
```

- [ ] **Step 7: Commit**

```bash
git add core/recovery/revision_tracker.py core/subtitle_editing/global_undo_manager.py tests/test_revision_tracker.py
git commit -m "feat: track monotonic editing revisions"
```

---

### Task 4: AtomicSnapshotStore

**Files:**
- Create: `core/recovery/atomic_snapshot_store.py`
- Create: `tests/test_recovery_atomicity.py`

**Interfaces:**
- Produces: `AtomicSnapshotStore.write_json_atomic(path: Path, payload: dict) -> None`
- Produces: `AtomicSnapshotStore.read_json(path: Path) -> dict`
- Consumers: RecoveryManager.

- [ ] **Step 1: Write failing atomicity tests**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.recovery.atomic_snapshot_store import AtomicSnapshotStore


class TestAtomicSnapshotStore(unittest.TestCase):
    def test_write_json_atomic_replaces_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.json"
            store = AtomicSnapshotStore()
            store.write_json_atomic(target, {"revision": 1})
            self.assertEqual(json.loads(target.read_text("utf-8"))["revision"], 1)
            self.assertFalse((Path(temp_dir) / "snapshot.tmp").exists())

    def test_replace_failure_preserves_previous_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "snapshot.json"
            target.write_text('{"revision":1}', encoding="utf-8")
            store = AtomicSnapshotStore()
            with patch("core.recovery.atomic_snapshot_store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    store.write_json_atomic(target, {"revision": 2})
            self.assertEqual(json.loads(target.read_text("utf-8"))["revision"], 1)
```

- [ ] **Step 2: Run tests RED**

```bash
python -m unittest discover -s tests -p "test_recovery_atomicity.py" -v
```

- [ ] **Step 3: Implement atomic writing**

Required implementation order:

```python
path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = path.with_suffix(".tmp")
with open(tmp_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(tmp_path, path)
```

After replace, attempt parent-directory fsync only where supported; failure to open/fsync the directory on Windows must not invalidate an already successful `os.replace`.

On failure before replace, best-effort remove the temp file and re-raise.

- [ ] **Step 4: Run atomicity tests GREEN**

```bash
python -m unittest discover -s tests -p "test_recovery_atomicity.py" -v
```

- [ ] **Step 5: Commit**

```bash
git add core/recovery/atomic_snapshot_store.py tests/test_recovery_atomicity.py
git commit -m "feat: add atomic recovery snapshot storage"
```

---

### Task 5: RecoveryManager Session Lifecycle, Delta Autosave, Candidate Scan, Quarantine

**Files:**
- Create: `core/recovery/recovery_manager.py`
- Create: `tests/test_recovery_manager.py`

**Interfaces:**
- Consumes: `RevisionTracker`, `AtomicSnapshotStore`, `RecoveryValidator`, recovery dataclasses, RuntimePaths-provided directories.
- Produces: the `RecoveryManager` interface defined in the Locked Spec.
- Consumers: bootstrap/MainWindow integration.

- [ ] **Step 1: Write TC90 and session creation tests**

The test must prove `create_session()` creates exactly:

```text
<session>/manifest.json
<session>/active.lock
```

and no `snapshot.json` before a dirty delta exists.

Write TC90 with a fake tracker state:

```python
def test_tc90_write_snapshot_skips_without_revision_delta(self):
    session = self.manager.create_session(self.context)
    state = self.make_state(edit_revision=0)
    self.assertFalse(self.manager.write_snapshot(state))
    self.assertFalse((session.directory / "snapshot.json").exists())
```

Then transition tracker to dirty revision 1 and assert one durable snapshot is written and tracker snapshot revision becomes 1.

- [ ] **Step 2: Run manager tests RED**

```bash
python -m unittest discover -s tests -p "test_recovery_manager.py" -v
```

- [ ] **Step 3: Implement session creation and manifest persistence**

`create_session()` must:

```text
generate UUID if context has no session ID
create session directory
write active.lock
write manifest atomically
store the active RecoverySession on manager
```

The lock file may contain a small diagnostic JSON payload (`session_id`, `created_at`) but recovery correctness depends on existence, not PID.

- [ ] **Step 4: Implement delta-aware write_snapshot()**

Return `False` without disk mutation when:

```text
not revision_tracker.is_dirty
OR edit_revision <= snapshot_revision
```

unless `force=True`.

On success:

```text
write snapshot atomically
update in-memory manifest edit_revision/snapshot_revision/last_snapshot_at
write manifest atomically
revision_tracker.record_snapshot_success(revision)
emit snapshot_written(session_id, revision)
return True
```

If snapshot or manifest persistence fails, do not call `record_snapshot_success()`.

- [ ] **Step 5: Write and implement TC92 candidate formula**

Build session fixtures for these cases:

```text
lock missing → not candidate
snapshot missing → not candidate
snapshot_revision == last_saved_revision → not candidate
snapshot_revision == last_clean_revision → not candidate
snapshot_revision > max(saved, clean) → candidate
```

`scan_candidates()` must never mutate valid candidate directories.

- [ ] **Step 6: Write and implement TC93 corrupt-session quarantine**

Create malformed JSON under a locked session, run `scan_candidates()`, and assert:

```text
no candidate returned
original session directory removed
quarantine/<session>-<timestamp>/ exists
```

Quarantine must emit `session_quarantined(session_id, reason)` and startup-facing callers can continue.

- [ ] **Step 7: Write and implement TC94 source mismatch classification**

A candidate with valid schema but missing or mismatched media must return a validation result with:

```text
is_valid == True
source_matches == False
source_reason in {SOURCE_MISSING, SOURCE_MISMATCH}
```

It must not be quarantined.

- [ ] **Step 8: Run manager tests GREEN**

```bash
python -m unittest discover -s tests -p "test_recovery_manager.py" -v
```

- [ ] **Step 9: Commit**

```bash
git add core/recovery/recovery_manager.py tests/test_recovery_manager.py
git commit -m "feat: manage recovery sessions and candidates"
```

---

### Task 6: Recovery Handoff, Explicit Save, Discard, and Clean Shutdown

**Files:**
- Modify: `core/recovery/recovery_manager.py`
- Modify: `tests/test_recovery_manager.py`
- Create: `tests/test_recovery_end_to_end.py`

**Interfaces:**
- Produces robust `handoff_recovered_state()`, `record_explicit_save()`, `discard_session()`, `finalize_clean_shutdown()`.
- Consumers: MainWindow/bootstrap.

- [ ] **Step 1: Write TC96 Recovery Handoff failure test**

Arrange Session A as valid candidate. Patch Session B snapshot persistence to fail before `os.replace`. Assert:

```text
handoff raises/returns failure
Session A directory still exists
Session A active.lock still exists
Session A snapshot.json still exists
```

- [ ] **Step 2: Implement handoff ordering**

`handoff_recovered_state()` must execute exactly:

```text
validate old candidate
create Session B + active.lock
force write recovered state to B
verify B snapshot exists and tracker snapshot revision committed
only then discard/archive Session A
return Session B
```

Never place deletion of Session A in `finally`.

- [ ] **Step 3: Write TC97 explicit-save cleanup**

After successful recovery + canonical Save notification:

```text
last_saved_revision == edit_revision
last_clean_revision == edit_revision
recovered_dirty_baseline == False
undo stack is clean
obsolete snapshot does not remain a recovery candidate
```

- [ ] **Step 4: Implement record_explicit_save()**

Ordering:

```text
caller confirms canonical save succeeded
→ revision_tracker.record_explicit_save_success()
→ update manifest saved/clean/edit revisions
→ delete obsolete snapshot.json
→ persist manifest
```

Do not remove `active.lock` because the application session is still alive.

- [ ] **Step 5: Write TC98 and TC99**

TC98: `discard_session()` removes lock, snapshot, manifest, and session directory so a restart cannot offer recovery.

TC99 is primarily a UI task later, but add manager-level proof that doing nothing leaves all session files unchanged; this gives the close guard a no-op primitive for Cancel.

- [ ] **Step 6: Implement finalize_clean_shutdown()**

For a clean working state or an already explicitly discarded/saved session:

```text
remove active.lock
remove stale snapshot
remove manifest/session directory when empty
```

Do not call this for a crash path.

- [ ] **Step 7: Run recovery manager/end-to-end tests**

```bash
python -m unittest discover -s tests -p "test_recovery_manager.py" -v
python -m unittest discover -s tests -p "test_recovery_end_to_end.py" -v
```

- [ ] **Step 8: Commit**

```bash
git add core/recovery/recovery_manager.py tests/test_recovery_manager.py tests/test_recovery_end_to_end.py
git commit -m "feat: protect recovery handoff and cleanup"
```

---

### Task 7: SingleInstanceGuard and Whitelisted IPC

**Files:**
- Create: `core/runtime/single_instance_guard.py`
- Create: `tests/test_single_instance_guard.py`

**Interfaces:**
- Produces: `IpcAction`, `IpcRequest`, `SingleInstanceGuard.try_acquire_primary()`, `relay_to_primary()`, `start_listening()`, `close()`.
- Consumer: `main.py` bootstrap and MainWindow IPC routing.

- [ ] **Step 1: Write TC101 protocol validation tests first**

```python
import unittest

from core.runtime.single_instance_guard import IpcAction, IpcRequest


class TestIpcProtocol(unittest.TestCase):
    def test_tc101_only_whitelisted_actions_parse(self):
        self.assertEqual(
            IpcRequest.from_dict({"action": "ACTIVATE_WINDOW"}).action,
            IpcAction.ACTIVATE_WINDOW,
        )
        self.assertEqual(
            IpcRequest.from_dict({"action": "OPEN_PROJECT", "path": "C:/p"}).action,
            IpcAction.OPEN_PROJECT,
        )
        self.assertEqual(
            IpcRequest.from_dict({"action": "OPEN_MEDIA", "path": "C:/v.mp4"}).action,
            IpcAction.OPEN_MEDIA,
        )
        with self.assertRaises(ValueError):
            IpcRequest.from_dict({"action": "RUN_COMMAND", "path": "calc.exe"})
```

- [ ] **Step 2: Implement enum/dataclass serialization**

Rules:

```text
ACTIVATE_WINDOW → path must be None/absent
OPEN_PROJECT → non-empty string path required
OPEN_MEDIA → non-empty string path required
unknown key/action → reject
payload serialized as UTF-8 JSON
```

Enforce a maximum received payload size such as 64 KiB before JSON decoding.

- [ ] **Step 3: Write TC100 primary/secondary relay test**

Create one `QCoreApplication` in the test module, start primary with a unique server name, connect `request_received`, then create a second guard instance and call `relay_to_primary()`.

Assert:

```text
primary receives one validated IpcRequest
secondary receives ACK
relay_to_primary returns True
```

- [ ] **Step 4: Implement QLocalServer/QLocalSocket handshake**

Wire format:

```json
{"action":"ACTIVATE_WINDOW"}
{"ok":true}
```

Primary writes ACK only after successful parse/validation and signal emission.

- [ ] **Step 5: Write and implement TC102 stale endpoint takeover**

Simulate a stale local server endpoint by ensuring no live socket accepts connection but the server name cannot initially listen. The guard must call `QLocalServer.removeServer(server_name)` only after the live-connect probe fails, then retry `listen()` and become primary.

- [ ] **Step 6: Run IPC tests GREEN**

```bash
python -m unittest discover -s tests -p "test_single_instance_guard.py" -v
```

- [ ] **Step 7: Commit**

```bash
git add core/runtime/single_instance_guard.py tests/test_single_instance_guard.py
git commit -m "feat: enforce single-instance IPC runtime"
```

---

### Task 8: Recovery Dialogs and Bootstrap Ordering

**Files:**
- Create: `ui/dialogs/recovery_dialog.py`
- Create: `ui/dialogs/source_mismatch_dialog.py`
- Modify: `main.py`
- Create: `tests/test_recovery_ui_integration.py`

**Interfaces:**
- Consumes: `SingleInstanceGuard`, `RecoveryManager`, candidate validation results.
- Produces bootstrap decision passed into `MainWindow` without writing canonical files.

- [ ] **Step 1: Add testable bootstrap request parser**

Before touching `main()`, add a pure helper in `main.py`:

```python
def build_ipc_request(argv: list[str]) -> IpcRequest:
    if len(argv) < 2:
        return IpcRequest(IpcAction.ACTIVATE_WINDOW)
    path = os.path.abspath(argv[1])
    if os.path.isdir(path) and path.endswith(".ai-subtitle"):
        return IpcRequest(IpcAction.OPEN_PROJECT, path)
    return IpcRequest(IpcAction.OPEN_MEDIA, path)
```

Test no-arg, project-dir, and media-file routing.

- [ ] **Step 2: Refactor `main()` so heavy runtime never starts in secondary process**

Required order:

```text
RuntimePaths.ensure_user_data_dirs()
QApplication
SingleInstanceGuard.try_acquire_primary()
if secondary:
    relay build_ipc_request(sys.argv)
    guard.close()
    return 0 on ACK, non-zero on failure
primary:
    start listening
    construct lightweight recovery bootstrap dependencies
    scan candidates
    present recovery decision when needed
    construct MainWindow
    apply bootstrap recovery result
    show window
    app.exec()
```

`MainWindow()` must not be constructed before primary ownership is known.

- [ ] **Step 3: Implement `RecoveryDialog`**

Public result enum:

```python
class RecoveryChoice(Enum):
    RESTORE = "restore"
    DISCARD = "discard"
```

Dialog displays project/session/timestamp and only these two actions.

- [ ] **Step 4: Implement `SourceMismatchDialog`**

Public result enum:

```python
class SourceMismatchChoice(Enum):
    RESTORE_UNLINKED = "restore_unlinked"
    DISCARD = "discard"
```

No linked restore button is present when the source guard fails.

- [ ] **Step 5: Add bootstrap behavior tests**

Test that a secondary-path helper does not instantiate MainWindow by patching `ui.Gui.MainWindow` and asserting it is untouched when the instance guard reports secondary.

Test corrupt recovery candidates are quarantined and startup proceeds with no recovery dialog.

- [ ] **Step 6: Run bootstrap/UI tests GREEN**

```bash
python -m unittest discover -s tests -p "test_recovery_ui_integration.py" -v
python -m unittest discover -s tests -p "test_single_instance_guard.py" -v
```

- [ ] **Step 7: Commit**

```bash
git add main.py ui/dialogs/recovery_dialog.py ui/dialogs/source_mismatch_dialog.py tests/test_recovery_ui_integration.py
git commit -m "feat: add recovery startup and dialogs"
```

---

### Task 9: MainWindow Recovery Wiring, Canonical Save, Close Guard, Autosave Timer, IPC Routing

**Files:**
- Modify: `ui/Gui.py`
- Modify: `core/services/workspace_service.py`
- Modify: `core/services/project_service.py`
- Modify: `tests/test_recovery_ui_integration.py`
- Modify: `tests/test_recovery_end_to_end.py`

**Interfaces:**
- Consumes: `RevisionTracker`, `RecoveryManager`, `RecoveryWorkingState`, `IpcRequest`.
- Produces: canonical working-state capture/apply methods and close/save behavior required by the spec.

- [ ] **Step 1: Inject RevisionTracker and RecoveryManager beside GlobalUndoManager**

In `MainWindow.__init__`, create/receive dependencies in this ownership order:

```text
ArtifactStore
ProjectService
GlobalUndoManager
RevisionTracker(GlobalUndoManager)
RecoveryManager(...RevisionTracker...)
WorkspaceService
```

Connect:

```text
RevisionTracker.dirty_changed → update title marker
RevisionTracker.clean_point_reached → RecoveryManager.invalidate_snapshot_at_clean_point
```

Do not use `project.state.dirty` as the close/recovery truth after this task.

- [ ] **Step 2: Add canonical working-state capture/apply methods**

Use exact MainWindow methods:

```python
def capture_recovery_working_state(self) -> RecoveryWorkingState:
    """Capture canonical segments plus ProjectState.workspace without persisting canonical files."""


def apply_recovery_working_state(
    self,
    state: RecoveryWorkingState,
    *,
    linked: bool,
) -> None:
    """Load recovered RAM state, clear undo history, restore workspace/playhead, remain dirty."""
```

Capture must call `workspace_service.capture_workspace()` first and deep-copy `sub_editor.all_segments` into pure JSON-compatible dicts.

Apply must:

```text
set editor canonical segments
render editor
refresh timeline data provider/widget
clear selection then restore selected_segment_id if present
restore playback position/workspace
GlobalUndoManager.clear()
RevisionTracker.restore_from_snapshot(...)
show recovered title marker
```

For unlinked restore, do not attempt to load missing/mismatched media.

- [ ] **Step 3: Start the 30-second delta-aware QTimer**

Create one `QTimer(self)` with `setInterval(30_000)`.

On timeout:

```text
if RevisionTracker.is_dirty
AND edit_revision > snapshot_revision:
    state = capture_recovery_working_state()
    RecoveryManager.write_snapshot(state)
```

No timer tick performs canonical Save.

- [ ] **Step 4: Normalize explicit Save semantics**

Refactor `action_save_project()` so the success path is deterministic:

```text
capture workspace
persist canonical project/draft state
if persistence raises/fails:
    show error
    keep revisions/recovery unchanged
else:
    RevisionTracker.record_explicit_save_success()
    GlobalUndoManager.mark_saved()
    RecoveryManager.record_explicit_save()
    clear title dirty marker
```

If `ProjectService.save_project()` currently cannot report failure except by exception, keep exception semantics and only run revision cleanup after it returns normally.

`SubEditor.save_draft()` when invoked as the canonical user Save path must notify the same success boundary rather than maintaining an independent saved-state interpretation.

- [ ] **Step 5: Add export shortcut without save mutation**

Bind `Ctrl+Shift+E` (or the locked export shortcut chosen in UI) to existing export workflow.

Add TC104 asserting after export:

```text
last_saved_revision unchanged
undo clean state unchanged
RevisionTracker.is_dirty unchanged
```

- [ ] **Step 6: Replace closeEvent dirty source and cleanup matrix**

Use:

```python
if self.revision_tracker.is_dirty:
```

Save branch:

```text
call explicit Save
if save unsuccessful → ignore close
if successful → recovery finalization then close
```

Discard branch:

```text
RecoveryManager.discard_session(active_session_id)
close without writing canonical state
```

Cancel branch:

```text
event.ignore()
return
```

Clean close:

```text
RecoveryManager.finalize_clean_shutdown()
```

- [ ] **Step 7: Add IPC request routing on primary MainWindow**

Implement:

```python
def handle_ipc_request(self, request: IpcRequest) -> None:
```

Rules:

```text
ACTIVATE_WINDOW → showNormal if minimized, raise_, activateWindow
OPEN_PROJECT    → invoke existing project-open workflow for path, then activate
OPEN_MEDIA      → add/open media through existing queue/project switching workflow, then activate
```

Do not introduce a second path for project/media loading.

- [ ] **Step 8: Run UI integration tests**

```bash
python -m unittest discover -s tests -p "test_recovery_ui_integration.py" -v
python -m unittest discover -s tests -p "test_recovery_end_to_end.py" -v
python -m unittest discover -s tests -p "test_editor_ui.py" -v
```

- [ ] **Step 9: Commit**

```bash
git add ui/Gui.py core/services/workspace_service.py core/services/project_service.py tests/test_recovery_ui_integration.py tests/test_recovery_end_to_end.py
git commit -m "feat: integrate recovery lifecycle with workspace"
```

---

### Task 10: Full End-to-End Acceptance TC95–TC104 and Regression Closure

**Files:**
- Modify: `tests/test_recovery_end_to_end.py`
- Modify: `.github/workflows/ci.yml` only if the existing workflow does not already discover the new tests.

**Interfaces:**
- Consumes all Sprint 11 components.
- Produces release/merge evidence only; no new production API.

- [ ] **Step 1: Implement TC95 canonical-file non-overwrite test**

Flow:

```text
create canonical Draft/project fixture
write recovery snapshot with newer text
restore working state
assert canonical file bytes unchanged
perform explicit Save
assert canonical file now changes to recovered state
```

- [ ] **Step 2: Implement TC96 second-crash handoff end-to-end test**

Exercise actual `RecoveryManager.handoff_recovered_state()` with a simulated Session B write failure and verify Session A remains valid/candidate.

Then run again without failure and verify:

```text
Session B valid
Session A removed only after B durable snapshot
```

- [ ] **Step 3: Implement TC97–TC99 close/save/discard matrix tests**

Use a MainWindow test double or patch QMessageBox return values:

```text
Save    → canonical save + no recovery candidate + window may close
Discard → no canonical save + session deleted + window may close
Cancel  → canonical/recovery state unchanged + close ignored
```

- [ ] **Step 4: Implement TC103 complete workflow**

```text
load project
edit subtitle
revision increments
force recovery snapshot
simulate crash by leaving lock/session intact
construct new recovery bootstrap
restore snapshot
assert same UUID/text/selection/playhead/workspace
assert undo history empty
assert recovered state dirty
explicit Save
assert recovered baseline cleared and recovery snapshot obsolete
```

- [ ] **Step 5: Implement TC104 export-is-not-save test**

Capture `last_saved_revision`, dirty state, and undo clean state before export. Execute export service/UI trigger against a temp destination. Assert all three state values are unchanged.

- [ ] **Step 6: Run all Sprint 11 tests**

```bash
python -m unittest discover -s tests -p "test_recovery_*.py" -v
python -m unittest discover -s tests -p "test_revision_tracker.py" -v
python -m unittest discover -s tests -p "test_single_instance_guard.py" -v
```

Expected: all TC85–TC104 acceptance coverage GREEN.

- [ ] **Step 7: Run complete repository test suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all existing Sprint 10 tests plus Sprint 11 tests PASS with zero failures/errors.

- [ ] **Step 8: Compile production and test modules**

```bash
python -m compileall core ui workers tests main.py
```

Expected: exit code 0.

- [ ] **Step 9: Confirm CI discovery**

The current workflow already runs unittest discovery from `tests`. If unchanged, do not modify CI. If it uses an explicit old file list, change it to:

```bash
python -m unittest discover -s tests -v
```

and retain existing offscreen/Xvfb Qt setup.

- [ ] **Step 10: Commit final acceptance tests**

```bash
git add tests/test_recovery_end_to_end.py .github/workflows/ci.yml
git commit -m "test: close Sprint 11 recovery acceptance coverage"
```

If `.github/workflows/ci.yml` was not modified, omit it from `git add`.

---

## Required Review Checkpoints

After each task, the reviewer must verify both the task-specific tests and architectural boundaries before proceeding.

1. **After Task 1:** no duplicate fingerprint algorithm remains in Recovery code.
2. **After Task 3:** no code increments revision from both `state_changed` and `clean_changed`.
3. **After Task 4:** snapshot writes are temp + flush/fsync + replace, never direct overwrite.
4. **After Task 5:** valid source mismatch is not quarantined; only corrupt/unsupported recovery data is quarantined.
5. **After Task 6:** Session A deletion occurs strictly after Session B durable snapshot success.
6. **After Task 7:** secondary process cannot instantiate heavy runtime and IPC has no arbitrary action channel.
7. **After Task 9:** close guards and title dirty marker use `RevisionTracker`, not `ProjectState.dirty`/raw `QUndoStack` alone.
8. **After Task 10:** export does not mutate saved revision and complete regression suite is green.

## Final Verification Commands

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
```

The branch is ready for PR review only when both commands succeed and TC85–TC104 (or equivalent named coverage) are present and green.
