# Sprint 11 — Project Reliability & Recovery

**Status:** Locked Design Spec  
**Date:** 2026-09-01  
**Target branch:** `sprint-11`  
**Base:** `master` after Sprint 10  

## 1. Goal

Sprint 11 makes subtitle editing resilient to crash, forced process termination, power loss, accidental close, and duplicate application launches without changing the meaning of explicit user saves.

The central rule is:

> Recovery protects the temporary working session; it never silently becomes an explicit user commit.

The sprint introduces four coordinated boundaries:

1. **Single-instance runtime** — one AI Subtitle Studio process owns GPU/media/runtime resources.
2. **Revision tracking** — a monotonic revision source of truth that cooperates with, but is not defined by, `QUndoStack`.
3. **Recovery snapshots** — atomic, delta-aware working-state snapshots stored outside project/SRT files.
4. **Safe lifecycle handling** — startup recovery, explicit save, discard, cancel, clean close, crash handoff, and source mismatch handling.

## 2. Non-goals

Sprint 11 does **not** include:

- Find/Replace.
- Translation or Local LLM features.
- Serialization of `QUndoStack` / `QUndoCommand` history.
- Automatic overwrite of `.srt`, Draft, or project files.
- Multiple simultaneous application instances.
- Cloud backup or synchronization.
- General arbitrary-command IPC.
- Recovery of running Whisper/VAD worker execution state; only canonical editable working state is recovered.

## 3. Existing Architecture Constraints

Sprint 11 extends existing boundaries rather than replacing them:

- `GlobalUndoManager` owns the single `QUndoStack` used by Editor and Timeline.
- `ProjectService` owns canonical project/draft persistence.
- `WorkspaceState` already owns UI restoration data such as page, tab, selection, playhead, preview state, and splitter sizes.
- `RuntimePaths` owns writable application-data locations under `%LOCALAPPDATA%/AI Subtitle Studio` on Windows.
- `main.py` is the process/bootstrap boundary and therefore owns single-instance acquisition before `MainWindow` becomes visible.

The recovery subsystem must not add another subtitle domain model. `segments[]` uses the canonical Sprint 10 segment schema (`id`, `stt`, `start`, `end`, `text`, `status`, `metadata`).

---

# 4. Locked Invariants

## 4.1 Single-instance invariant

Exactly one primary AI Subtitle Studio instance may own application runtime resources.

A secondary launch may only:

- activate the primary window;
- request `OPEN_PROJECT(path)`;
- request `OPEN_MEDIA(path)`;
- wait for ACK;
- exit with code `0` after successful relay.

A secondary process never scans or mutates recovery sessions.

## 4.2 Recovery storage invariant

Recovery state is independent from explicit project files:

```text
%LOCALAPPDATA%/
└── AI Subtitle Studio/
    └── recovery/
        ├── sessions/
        │   └── <session_id>/
        │       ├── manifest.json
        │       ├── snapshot.json
        │       └── active.lock
        └── quarantine/
            └── <session_id>-<timestamp>/
```

`active.lock` is session-scoped. There is no global recovery lockfile.

## 4.3 Atomic snapshot invariant

`snapshot.json` is never updated in-place.

```text
serialize canonical state
→ write snapshot.tmp
→ flush
→ fsync(file)
→ os.replace(snapshot.tmp, snapshot.json)
→ fsync parent directory where supported/practical
→ update manifest atomically
```

If the process dies during the write, either the previous valid snapshot or the new valid snapshot remains available.

## 4.4 Explicit-save invariant

Only a successful canonical save changes `last_saved_revision`.

The following are explicit commits:

- Save Draft / canonical subtitle state.
- Save Project when it persists the current canonical editable state.
- `Ctrl+S` routed to the above canonical save operation.

The following do **not** change `last_saved_revision`:

- Export SRT/VTT/TXT.
- Burn hardsub / export video.
- Recovery snapshot.
- Preview operations.

## 4.5 Monotonic revision invariant

`edit_revision` never decreases during one working session.

Each successful canonical state transition increments the revision exactly once:

- command push/redo;
- undo;
- redo;
- Add/Delete/Split/Merge through the shared command stack;
- future canonical edit commands.

Snapshot writes do not increment it.

```text
snapshot_revision = edit_revision     # after successful atomic snapshot
last_saved_revision = edit_revision   # after successful explicit save
```

### Qt signal-order normalization

`QUndoStack.cleanChanged(True)` must **not** cause a second revision increment after an Undo/Redo that already incremented `edit_revision`.

The tracker records exactly one revision per canonical state transition, then evaluates whether the resulting stack is at its clean point. `cleanChanged` may be observed as a hint/UI signal, but revision mutation occurs through one post-transition path.

This resolves the otherwise ambiguous double-increment case.

## 4.6 Dirty-state invariant

`RevisionTracker` is the source of truth for project working-state dirtiness.

```text
is_dirty = recovered_dirty_baseline OR not undo_stack.isClean()
```

`GlobalUndoManager.is_dirty` may remain as a legacy/raw stack view, but close guards, recovery scheduling, title dirty marker, and persistence decisions must use `RevisionTracker.is_dirty`.

## 4.7 Undo-to-clean invariant

For an ordinary non-recovered session, when a command transition finishes with the stack at the explicit-save clean point:

```text
last_clean_revision = edit_revision
```

Any stale recovery snapshot older than/equal to this disk-safe clean point is invalidated or removed immediately.

Important recovered-session exception:

> `QUndoStack.isClean() == True` does not imply disk-safe state while `recovered_dirty_baseline == True`.

After a recovery restore, the stack starts empty/clean only because history is intentionally discarded. Undoing later edits back to the recovered baseline must **not** update `last_clean_revision`, clear `recovered_dirty_baseline`, or delete the recovery snapshot. Only an explicit save can make that recovered baseline disk-safe.

## 4.8 Recovery candidate invariant

A session is a recoverable crash candidate only when all required storage is present and:

```text
active.lock exists
AND snapshot.json exists
AND snapshot_revision > max(last_saved_revision, last_clean_revision)
```

Before presenting Restore, candidate validation must also pass schema and source checks.

## 4.9 Recovery restore invariant

Restoring a snapshot changes RAM/working state only.

It must not overwrite the original project, Draft, or exported subtitle file.

After restore:

```text
load canonical working state
GlobalUndoManager.clear()
edit_revision = snapshot_revision
recovered_dirty_baseline = True
is_dirty = True
```

Window/title semantics:

```text
<Project Name> (Đã khôi phục - Chưa lưu) *
```

Undo history begins fresh from the recovered state.

## 4.10 Recovery handoff invariant

A recovered Session A is not deleted until the recovered state is durably anchored in the new Session B.

```text
validate Session A
→ load A snapshot into RAM
→ create Session B + active.lock
→ force-write A state as B/snapshot.tmp
→ flush + fsync + os.replace to B/snapshot.json
→ persist B manifest
→ only then delete/archive Session A
→ render/show recovered workspace
```

This removes the crash-after-recovery vulnerability window.

## 4.11 Close/discard invariant

| Working state | User action | Recovery behavior | Application behavior |
|---|---|---|---|
| Clean | Close | remove lock + cleanup session | exit |
| Dirty | Save | explicit save; update revisions; cleanup | exit |
| Dirty | Don't Save | delete recovery session completely | discard changes + exit |
| Dirty | Cancel | keep recovery/session | remain open |
| Crash/Kill/Power loss | none | lock + last durable snapshot remain | recovery offered next startup |

`Don't Save` is an explicit discard decision. The discarded state must not reappear as a recovery prompt on the next launch.

---

# 5. Proposed Directory Structure

```text
core/
├── recovery/
│   ├── __init__.py
│   ├── recovery_manager.py
│   ├── recovery_models.py
│   ├── recovery_validator.py
│   ├── atomic_snapshot_store.py
│   └── revision_tracker.py
│
├── runtime/
│   ├── runtime_paths.py                 # extend recovery path getters
│   └── single_instance_guard.py
│
├── project/
│   ├── project_state.py
│   └── source_fingerprint.py            # shared source hash helper
│
ui/
├── dialogs/
│   ├── recovery_dialog.py
│   └── source_mismatch_dialog.py
└── Gui.py                               # close guard + recovered-state application

main.py                                  # bootstrap / single-instance / recovery scan

tests/
├── test_revision_tracker.py
├── test_recovery_manager.py
├── test_recovery_atomicity.py
├── test_recovery_integration.py
├── test_single_instance_guard.py
└── test_close_guard.py
```

### Why extract `source_fingerprint.py`

`ProjectService` already fingerprints media. Recovery startup also needs the same algorithm before `MainWindow` is shown. Duplicating hashing logic would create incompatible source guards. The existing fingerprint algorithm should move behind one reusable function/service and both `ProjectService` and Recovery validation should depend on it.

---

# 6. RuntimePaths Extensions

`RuntimePaths` remains the only owner of writable application-data paths.

Required getters:

```python
class RuntimePaths:
    @staticmethod
    def get_recovery_dir() -> Path: ...

    @staticmethod
    def get_recovery_sessions_dir() -> Path: ...

    @staticmethod
    def get_recovery_quarantine_dir() -> Path: ...
```

`ensure_user_data_dirs()` creates these directories at startup.

No recovery component hardcodes `%LOCALAPPDATA%` or application directory paths.

---

# 7. Data Models

## 7.1 Recovery manifest

`manifest.json` is lifecycle metadata, not the subtitle payload.

```json
{
  "schema_version": 1,
  "session_id": "uuid",
  "app_version": "...",
  "project_id": "uuid-or-null",
  "project_file_path": "...",
  "video_path": "...",
  "source_fingerprint": "sha256",
  "source_modified_at": 0.0,
  "created_at": "ISO-8601",
  "last_snapshot_at": "ISO-8601-or-null",
  "edit_revision": 42,
  "snapshot_revision": 40,
  "last_saved_revision": 35,
  "last_clean_revision": 35
}
```

`active.lock` existence is the crash/session-liveness marker. PID is not required for recovery correctness because single-instance ownership is established first.

## 7.2 Recovery snapshot

`snapshot.json` stores only canonical working state.

```json
{
  "schema_version": 2.0,
  "session_id": "uuid",
  "project_id": "uuid-or-null",
  "project_file_path": "...",
  "video_path": "...",
  "source_fingerprint": "sha256",
  "edit_revision": 42,
  "segments": [],
  "workspace_state": {
    "active_page": "subtitle_editor",
    "active_tab": "inline_editor",
    "selected_segment_id": "uuid-or-null",
    "playback_position_ms": 12345,
    "subtitle_preview_enabled": true,
    "splitter_sizes": [400, 200]
  }
}
```

Logical snapshot scope includes `selected_segment_id` and `playback_position_ms`; physically they stay inside `workspace_state` because the existing `WorkspaceState` already owns them. They are not duplicated at the root, preventing two competing values.

No Undo/Redo command objects are serialized.

---

# 8. RevisionTracker Interface

`RevisionTracker` owns revision semantics and dirty truth. It does not write files.

```python
class RevisionTracker(QObject):
    dirty_changed = Signal(bool)
    revision_changed = Signal(int)
    clean_point_reached = Signal(int)

    def __init__(self, undo_manager: GlobalUndoManager, parent=None): ...

    @property
    def edit_revision(self) -> int: ...

    @property
    def snapshot_revision(self) -> int: ...

    @property
    def last_saved_revision(self) -> int: ...

    @property
    def last_clean_revision(self) -> int: ...

    @property
    def recovered_dirty_baseline(self) -> bool: ...

    @property
    def is_dirty(self) -> bool: ...

    def record_state_transition(self) -> int:
        """Increment edit_revision exactly once after a successful command state transition."""

    def record_snapshot_success(self, revision: int) -> None:
        """Set snapshot_revision after durable atomic snapshot completion."""

    def record_explicit_save_success(self) -> None:
        """Set saved/clean revisions to edit_revision and clear recovered baseline."""

    def restore_from_snapshot(
        self,
        snapshot_revision: int,
        last_saved_revision: int,
        last_clean_revision: int,
    ) -> None:
        """Reset runtime tracking around a recovered dirty baseline."""

    def reset_for_new_document(self) -> None: ...
```

### Integration with GlobalUndoManager

Existing `GlobalUndoManager.state_changed` is emitted after successful push/undo/redo operations. The tracker uses a single post-transition hook so revision is incremented once.

Conceptual integration:

```text
GlobalUndoManager push/undo/redo succeeds
→ state_changed
→ RevisionTracker.record_state_transition()
→ inspect undo_stack.isClean()
→ if clean AND not recovered_dirty_baseline:
       last_clean_revision = edit_revision
       emit clean_point_reached(edit_revision)
```

`RecoveryManager` listens to `clean_point_reached` and invalidates stale snapshot state.

`record_explicit_save_success()` is called only after the canonical save operation returns successfully. Failed saves do not modify saved revisions or clear dirty state.

---

# 9. RecoveryManager Interface

`RecoveryManager` owns recovery-session lifecycle and durable recovery storage. It contains no UI code.

```python
class RecoveryManager(QObject):
    snapshot_written = Signal(str, int)       # session_id, revision
    session_quarantined = Signal(str, str)    # session_id, reason

    def __init__(
        self,
        sessions_dir: Path,
        quarantine_dir: Path,
        revision_tracker: RevisionTracker,
        snapshot_store: AtomicSnapshotStore,
        validator: RecoveryValidator,
        parent=None,
    ): ...

    def create_session(self, context: RecoveryContext) -> RecoverySession: ...

    def scan_candidates(self) -> list[RecoveryCandidate]: ...

    def validate_candidate(
        self,
        candidate: RecoveryCandidate,
    ) -> RecoveryValidationResult: ...

    def write_snapshot(
        self,
        state: RecoveryWorkingState,
        *,
        force: bool = False,
    ) -> bool:
        """Write only when needed unless force=True; update revision only after durable success."""

    def invalidate_snapshot_at_clean_point(self, clean_revision: int) -> None: ...

    def record_explicit_save(self) -> None: ...

    def restore_candidate(
        self,
        candidate: RecoveryCandidate,
    ) -> RecoveryWorkingState: ...

    def handoff_recovered_state(
        self,
        old_candidate: RecoveryCandidate,
        recovered_state: RecoveryWorkingState,
        new_context: RecoveryContext,
    ) -> RecoverySession:
        """Create Session B and durably snapshot before removing Session A."""

    def discard_session(self, session_id: str) -> None: ...

    def quarantine_session(self, session_id: str, reason: str) -> Path: ...

    def finalize_clean_shutdown(self) -> None: ...
```

## Responsibilities

`RecoveryManager`:

- owns `manifest.json`, `snapshot.json`, and `active.lock` lifecycle;
- asks `RevisionTracker` for revision truth;
- skips periodic writes when there is no delta;
- never mutates original project/SRT files;
- performs recovery handoff before deleting an old crash session;
- cleans session data after explicit discard or clean shutdown;
- delegates JSON/schema/source validation to `RecoveryValidator`;
- delegates atomic file replacement to `AtomicSnapshotStore`.

It does **not**:

- render dialogs;
- edit `all_segments` directly;
- own `QUndoStack`;
- export subtitles;
- execute IPC requests.

---

# 10. Auto-save Scheduler

The scheduler is a `QTimer` with a 30-second interval owned by the application/session orchestration layer.

```text
Timer tick
↓
RevisionTracker.is_dirty?
│ no → skip
│ yes
↓
edit_revision > snapshot_revision?
│ no → skip
│ yes
↓
RecoveryManager.write_snapshot(current_working_state)
```

A successful write:

```text
atomic snapshot persisted
→ manifest persisted
→ RevisionTracker.record_snapshot_success(edit_revision)
```

A failed write:

- leaves `snapshot_revision` unchanged;
- leaves dirty state unchanged;
- logs the failure;
- keeps the previous valid snapshot;
- does not interrupt editing with repeated modal dialogs.

A direct recovery handoff uses `force=True` and does not wait for the 30-second timer.

---

# 11. RecoveryValidator & Source Guard

Validation order is fixed:

```text
read JSON
→ recovery schema version supported?
→ required root keys present?
→ canonical segment schema valid?
→ revision fields are non-negative and internally consistent?
→ session_id matches manifest?
→ source/project guard
```

## 11.1 Revision integrity

At minimum:

```text
edit_revision >= 0
snapshot_revision >= 0
last_saved_revision >= 0
last_clean_revision >= 0
snapshot_revision == snapshot.edit_revision
```

A candidate is only offered when its candidate invariant also passes.

## 11.2 Source guard

Recovery validates:

- expected project identity when available;
- original media path availability;
- source fingerprint using the same algorithm as `ProjectService`.

If the source path is missing/moved or fingerprint differs, automatic linked restore is blocked.

The user receives only:

1. **Restore as Unlinked Project** — recover subtitle working state without attaching the media; or
2. **Discard/Delete Recovery**.

No snapshot is silently applied to a different source.

## 11.3 Corruption / unsupported schema

Invalid recovery sessions are moved atomically/best-effort into:

```text
recovery/quarantine/<session_id>-<timestamp>/
```

The reason is logged. Startup continues normally. Corrupt recovery must never crash the application boot sequence.

---

# 12. SingleInstanceGuard / IPC Interface

The single-instance subsystem lives at the bootstrap/runtime boundary and uses `QLocalServer` / `QLocalSocket`.

```python
class IpcAction(str, Enum):
    ACTIVATE_WINDOW = "ACTIVATE_WINDOW"
    OPEN_PROJECT = "OPEN_PROJECT"
    OPEN_MEDIA = "OPEN_MEDIA"


@dataclass(frozen=True)
class IpcRequest:
    action: IpcAction
    path: str | None = None


class SingleInstanceGuard(QObject):
    request_received = Signal(object)  # validated IpcRequest

    def __init__(self, server_name: str, parent=None): ...

    def try_acquire_primary(self) -> bool:
        """Return True only for the process that owns the local server."""

    def relay_to_primary(
        self,
        request: IpcRequest,
        timeout_ms: int = 1500,
    ) -> bool:
        """Send one validated request, wait for ACK, then allow secondary exit."""

    def start_listening(self) -> None: ...

    def close(self) -> None: ...
```

## 12.1 IPC wire format

UTF-8 JSON, one request per connection:

```json
{"action":"ACTIVATE_WINDOW"}
{"action":"OPEN_PROJECT","path":"C:/..."}
{"action":"OPEN_MEDIA","path":"C:/..."}
```

ACK:

```json
{"ok":true}
```

Reject unknown actions, oversized payloads, malformed JSON, and invalid path shape. IPC is never a generic command execution channel.

## 12.2 Stale local-server endpoint

Primary acquisition sequence:

```text
attempt connection to existing server
├─ success → secondary; relay request and exit
└─ no live server
    → remove stale local endpoint if Qt/platform left one
    → listen
    → become primary
```

Recovery scanning happens only after primary ownership is established.

---

# 13. Bootstrap Sequence

`main.py` becomes the authoritative startup coordinator.

```text
RuntimePaths.ensure_user_data_dirs()
↓
QApplication
↓
SingleInstanceGuard
├─ existing primary
│   → build IpcRequest from argv
│   → relay + ACK
│   → exit 0
│
└─ primary acquired
    ↓
    Recovery bootstrap services
    ↓
    scan + pre-validate candidates
    ↓
    Recovery Dialog if valid candidate exists
    ├─ Restore linked
    ├─ Restore unlinked on source mismatch
    └─ Discard
    ↓
    create MainWindow
    ↓
    inject/apply bootstrap recovery result before show()
    ↓
    create/activate current recovery Session B
    ↓
    start 30s auto-save scheduler
    ↓
    show MainWindow
```

For a recovery handoff, Session B's forced durable snapshot is completed before Session A is removed and before the recovered workspace is exposed to normal user interaction.

---

# 14. MainWindow Integration

`MainWindow` remains UI orchestration only.

Required integration points:

- receives/injects `RevisionTracker` and `RecoveryManager` or a recovery/session coordinator;
- uses `RevisionTracker.is_dirty` for `*` title marker and close guard;
- provides a canonical working-state snapshot provider from `SubEditor.all_segments` + `WorkspaceState`;
- applies `RecoveryWorkingState` to Editor/Timeline/selection/playhead before first visible recovered frame;
- routes successful `Ctrl+S`/Save Project/Save Draft completion into `RevisionTracker.record_explicit_save_success()` and `RecoveryManager.record_explicit_save()`;
- routes Discard into `RecoveryManager.discard_session()`;
- routes Cancel to no lifecycle mutation;
- handles IPC `request_received` by activating/opening only through existing application workflows.

The current `closeEvent()` Save/Discard/Cancel UI can be retained but its dirty source and cleanup side effects must move to the Sprint 11 lifecycle semantics.

---

# 15. Canonical Save and Export Behavior

## Ctrl+S

```text
Ctrl+S
→ capture canonical working state
→ persist canonical project/draft state
→ success?
   no  → remain dirty; keep recovery
   yes → last_saved_revision = edit_revision
          last_clean_revision = edit_revision
          recovered_dirty_baseline = False
          GlobalUndoManager.mark_saved()
          invalidate/delete unnecessary recovery snapshot
          remove title '*'
```

## Export

```text
Ctrl+Shift+E / Export menu
→ Export SRT/VTT/TXT or media
→ no RevisionTracker save mutation
→ no mark_saved()
→ recovery state remains based on editable working state
```

---

# 16. Recovery Dialog UX

A valid crash candidate is shown before the main window becomes visible.

Normal candidate:

```text
AI Subtitle Studio phát hiện một phiên làm việc chưa được lưu.
Project: <name>
Snapshot: <timestamp>

[Khôi phục] [Bỏ qua]
```

Source mismatch:

```text
Không thể xác minh media gốc của phiên khôi phục.

[Khôi phục dạng Unlinked] [Xóa Snapshot]
```

Restore never implies Save.

After linked/unlinked restoration the recovered window remains dirty until the user explicitly saves or discards.

---

# 17. Failure Handling

| Failure | Required behavior |
|---|---|
| snapshot.tmp write fails | retain previous snapshot; do not advance revision |
| fsync fails | treat snapshot as failed; do not advertise new revision |
| os.replace fails | retain previous snapshot where possible; log |
| manifest update fails after snapshot replace | recover by validating snapshot/manifest conservatively; never delete previous session prematurely |
| corrupt JSON | quarantine session; continue startup |
| unsupported snapshot schema | quarantine/ignore with log; continue startup |
| media missing/moved | linked restore blocked; Unlinked/Discard only |
| fingerprint mismatch | linked restore blocked; Unlinked/Discard only |
| explicit Save fails | keep dirty/recovery state; do not update saved revisions |
| secondary IPC timeout | secondary exits non-successfully or shows concise error; it must not start a second heavy runtime instance |
| crash during recovery handoff | at least Session A or durable Session B must remain recoverable |

---

# 18. Test Strategy / Acceptance Criteria

Sprint 11 is not complete until these behaviors are covered by automated tests.

## RevisionTracker

**TC85 — Monotonic command revision**  
Push → Undo → Redo increments exactly once per transition.

**TC86 — Undo to saved clean point**  
After Save, edit then Undo back to clean → `last_clean_revision == edit_revision` and stale snapshot invalidates.

**TC87 — No double increment from cleanChanged**  
Undo that reaches clean point advances revision by exactly `+1`, not `+2`.

**TC88 — Recovered baseline remains dirty**  
Restore + empty clean `QUndoStack` still yields `RevisionTracker.is_dirty == True`.

**TC89 — Undo to recovered baseline is not disk-clean**  
Restore → edit → Undo to recovered baseline must preserve `recovered_dirty_baseline`, keep recovery, and not advance `last_clean_revision` as a disk-safe point.

## Atomic recovery

**TC90 — Delta-aware timer**  
No revision delta → no file rewrite. New dirty revision → one snapshot.

**TC91 — Atomic replacement failure**  
Simulated write/replace failure leaves previous valid snapshot and does not advance `snapshot_revision`.

**TC92 — Candidate formula**  
Only `active.lock + snapshot + snapshot_revision > max(saved, clean)` becomes candidate.

**TC93 — Corrupt snapshot quarantine**  
Malformed JSON cannot crash startup and session is moved to quarantine.

**TC94 — Source mismatch guard**  
Changed/missing/moved source blocks linked restoration.

## Recovery lifecycle

**TC95 — Crash recovery does not overwrite canonical file**  
Restore changes working state only; original project/Draft remains byte-identical until explicit Save.

**TC96 — Recovery handoff survives second crash**  
Session A remains until Session B durable snapshot succeeds. Simulated crash/failure before B commit leaves A recoverable.

**TC97 — Explicit Save cleans recovery**  
Successful canonical save updates saved/clean revisions, clears recovered baseline, marks undo clean, and removes obsolete snapshot.

**TC98 — Don't Save means permanent discard**  
Discard removes session/lock/snapshot and next startup has no recovery prompt.

**TC99 — Cancel close preserves session**  
Close Cancel leaves app and recovery session unchanged.

## Single instance / IPC

**TC100 — Secondary activate request**  
Second instance relays `ACTIVATE_WINDOW`, receives ACK, and does not create MainWindow/heavy AI services.

**TC101 — Open project/media IPC whitelist**  
Only the three allowed actions deserialize successfully.

**TC102 — Stale endpoint takeover**  
No live primary + stale server endpoint → new process safely becomes primary.

## End-to-end

**TC103 — Edit → snapshot → simulated crash → restore → save**  
Recovered segments, UUIDs, selection, playhead, and workspace state match snapshot; Undo starts empty; state remains dirty until Save.

**TC104 — Export does not commit working state**  
Exporting SRT/video does not modify `last_saved_revision` or mark undo clean.

---

# 19. Definition of Done

Sprint 11 is complete only when:

1. single-instance guard is active before heavy runtime/MainWindow initialization;
2. secondary launch relays only whitelisted IPC actions;
3. recovery session paths are owned by `RuntimePaths`;
4. `RevisionTracker` is the source of truth for close/recovery dirty state;
5. revisions are monotonic and increment exactly once per canonical transition;
6. undo-to-save clean points invalidate stale snapshots without false recovery;
7. recovered baseline remains dirty independently of `QUndoStack.isClean()`;
8. autosave writes only dirty deltas every 30 seconds;
9. snapshots are atomically written and previous valid data survives failures;
10. recovery snapshots never overwrite canonical files implicitly;
11. source mismatch is guarded and supports Unlinked/Discard only;
12. corrupt sessions are quarantined without boot failure;
13. recovery handoff guarantees old session deletion only after new durable snapshot;
14. Save / Don't Save / Cancel follow the locked close matrix;
15. Export never changes save revision semantics;
16. all Sprint 10 tests remain green;
17. TC85–TC104 or equivalent acceptance coverage is green in local suite and CI.

---

# 20. Implementation Boundaries Summary

```text
main.py
  ├─ SingleInstanceGuard
  ├─ Recovery bootstrap scan/dialog decision
  └─ MainWindow startup

GlobalUndoManager
  └─ command stack mechanics
        ↓
RevisionTracker
  ├─ edit_revision
  ├─ snapshot_revision
  ├─ last_saved_revision
  ├─ last_clean_revision
  └─ recovered_dirty_baseline
        ↓
RecoveryManager
  ├─ session lifecycle
  ├─ autosave decision
  ├─ candidate scan
  ├─ handoff
  └─ cleanup/quarantine
        ↓
AtomicSnapshotStore
  └─ tmp → flush/fsync → os.replace

ProjectService
  └─ explicit canonical commits only

ExportService
  └─ artifacts only; never marks project saved
```

This separation is the architectural contract for Sprint 11.
