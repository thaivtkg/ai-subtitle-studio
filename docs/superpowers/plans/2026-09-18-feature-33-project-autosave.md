# Feature 33 Project Autosave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add crash-safe dirty-project autosave scheduling and paired recovery-slot rotation without changing canonical persistence, manual-save ownership, or revision authority.

**Architecture:** Add a small `AutosaveCoordinator` that listens to `RevisionTracker.revision_changed`, owns only timer/generation/session scheduling state, and delegates capture/persistence to existing `MainWindow` and `RecoveryManager`. Extend `RecoveryManager` with paired current/previous/older recovery slots, semantic failure-stage boundaries, deterministic fallback scanning, and complete history cleanup.

**Tech Stack:** Python, PySide6 signals, existing `RevisionTracker`, `RecoveryManager`, `AtomicSnapshotStore`, `RecoveryValidator`, unittest fake scheduler.

**Spec:** `docs/superpowers/specs/2026-09-18-feature-33-project-autosave-design.md`

## Global Constraints

- Autosave never clears dirty state, performs manual save, writes canonical project/subtitle files, or restores recovery.
- `RevisionTracker.snapshot_revision` remains durable recovery progress truth.
- A callback must verify generation + session identity before capture and after capture before persistence.
- Inactivity debounce is 30 seconds; maximum dirty-cycle deadline is 120 seconds and never resets per edit.
- Recovery slots are paired `manifest.json`/`snapshot.json`, `.previous`, and `.older`; scanner fallback is current → previous → older → quarantine.
- No Recovery Center, ProjectState subtitle migration, background threads, or unrelated UI redesign.

### Task 1: Implement coordinator scheduling and lifecycle guards

**Files:**
- Create: `core/recovery/autosave_coordinator.py`
- Modify: `ui/Gui.py`
- Test: `tests/test_autosave_infrastructure.py`

**Interfaces:**
- `AutosaveCoordinator(revision_tracker, session_provider, snapshot_provider, persist_snapshot, scheduler, activity_logger=None)`.
- `start()`, `clear_session()`, `manual_save_succeeded()`, and `dispose()` are lifecycle operations.
- Scheduler provides `call_later(delay_ms, callback)` and `cancel(handle)`.

- [x] Subscribe to `revision_changed`, seed a dirty cycle when `start()` sees an already-dirty tracker, restart only inactivity timer on edits, and preserve the original 120-second deadline.
- [x] Capture `{generation, session_id}` before snapshot, deep-copy provider output, verify identity again, then call persistence.
- [x] Keep retry at 30 seconds only for dirty/new revision/current identity; do not call `record_snapshot_success` from the coordinator.
- [x] Replace MainWindow’s direct `QTimer` autosave with the coordinator and bind it to current recovery session/capture/persistence callbacks.
- [x] Cancel coordinator on clear, unload, session switch, manual save success, and shutdown; preserve existing public save behavior.
- [x] Run coordinator-focused tests and confirm failures move from missing class to recovery integration failures.

### Task 2: Add paired-slot rotation and semantic failure boundaries

**Files:**
- Modify: `core/recovery/recovery_manager.py`
- Modify: `core/recovery/atomic_snapshot_store.py` only if the existing atomic primitive needs a minimal helper
- Test: `tests/test_autosave_infrastructure.py`

**Interfaces:**
- Preserve `RecoveryManager.write_snapshot`, `scan_candidates`, `record_explicit_save`, `invalidate_snapshot_at_clean_point`, `discard_session`, and `finalize_clean_shutdown` public signatures.
- Add internal semantic stage callbacks usable by the RED-test failure store without depending on write-call counts.

- [x] Validate a complete new pair before rotation/publication.
- [x] Preserve current valid pair, publish older from previous, publish previous from current, and publish new current last; never destroy the only valid pair before final publication.
- [x] Roll back/leave recoverable state on any semantic stage failure and update tracker snapshot revision only after durable success.
- [x] Rotate manifest and snapshot together, including metadata consistency.
- [x] Run AS07–AS10 and AS09 semantic failure subtests.

### Task 3: Add scanner fallback and lifecycle cleanup

**Files:**
- Modify: `core/recovery/recovery_manager.py`
- Test: `tests/test_autosave_infrastructure.py`, existing recovery manager/end-to-end tests as needed

- [x] Scan each session’s current, previous, and older pairs independently but return only matching manifest/snapshot pairs.
- [x] Quarantine only when all slots are invalid; preserve active session metadata when explicit save or clean-point invalidation removes snapshot history.
- [x] Remove all six slot files during explicit-save cleanup, clean-point invalidation, discard, clean shutdown, and old-session switch according to existing lifecycle semantics.
- [x] Run PAIR01–PAIR05, CRASH-C01–C04, AS21–AS24 and existing recovery suites.

### Task 4: Integrate and regress

**Files:**
- Modify: `ui/Gui.py` only for coordinator lifecycle wiring if Task 1 leaves integration gaps
- Test: existing recovery, revision, persistence, MainWindow, and Feature 31 suites

- [x] Verify canonical project bytes, dirty state, saved revision, and restore behavior remain unchanged.
- [x] Run focused Feature 33 suite, recovery suites, revision tests, MainWindow lifecycle tests, and the full local suite.
- [ ] Review diff for production-only scope, commit implementation, push branch, and report CI status without merging.
