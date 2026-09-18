# Feature 33 — Project Autosave Infrastructure

**Status:** Approved design with safety locks  
**Date:** 2026-09-18  
**Base:** `d6a891aaa4ac743efe29591c53cf386e2232db2a`  
**Branch:** `feature/project-autosave`

## Goal and non-goals

Feature 33 adds crash-safe autosave snapshots for dirty, recoverable working
state. Autosave writes only the existing recovery session; it never performs a
manual project save, clears dirty state, overwrites the canonical project or
subtitle files, or restores state.

This feature does not add Recovery Center UI, automatic restore, preview,
diff, cloud storage, configurable intervals, project history, or background
worker threads.

## Existing architecture

- `RevisionTracker` is the dirty and revision authority.
- `ProjectService` owns canonical project persistence.
- `SubtitleEditorWidget.all_segments` remains the operational subtitle source.
- `RecoveryManager` already owns recovery sessions, startup scanning,
  manifests, and recovery handoff.
- `AtomicSnapshotStore` already provides temp-file, flush/fsync, and atomic
  replacement for JSON files.
- `RuntimePaths` owns the application recovery directory.
- Activity events use `MainWindow.append_log()` and the existing dashboard
  activity model.

No second recovery subsystem or revision authority will be introduced.

## Components and data flow

```text
RevisionTracker.revision_changed / dirty_changed
        ↓
AutosaveCoordinator
  - inactivity timer: 30 seconds
  - maximum dirty timer: 120 seconds
  - generation + project/source identity guard
        ↓
MainWindow.capture_recovery_working_state()
        ↓
RecoveryManager.write_snapshot()
        ↓
AtomicSnapshotStore
  snapshot.json
  snapshot.previous.json
  snapshot.older.json
```

`AutosaveCoordinator` owns only scheduling, ephemeral scheduling state,
source binding, and lifecycle cancellation. It does not own project data,
serialize canonical project state, mutate `RevisionTracker`, or restore
recovery state.

## Scheduling contract

The coordinator listens to `revision_changed`, not only `dirty_changed`.

When a dirty revision begins a cycle:

1. start the 120-second max-age timer once;
2. start/restart the 30-second inactivity timer for every relevant revision;
3. autosave when either timer fires, if the revision is still dirty and newer
   than the last successful snapshot;
4. after success, wait for a newer revision before starting another cycle.

The max-age timer is never restarted by later edits. A clean project never
gets an autosave. Repeated callbacks for the same revision do not write again.

## Identity and lifecycle safety

Each scheduled callback captures a monotonically increasing generation and the
existing project/source identity: project id, project path, source path and
source fingerprint where available.

The callback must verify generation and identity before capture, capture a
deep-copied working snapshot, then verify generation and identity again before
calling persistence. A source switch, unload, clear, new project, or shutdown
increments the generation and cancels both timers. A callback from Project A
therefore cannot publish Project B data into A's recovery session.

Manual save success cancels the pending cycle but leaves existing recovery
cleanup behavior unchanged. Autosave failure leaves editing, dirty state,
saved-revision state, and the last valid recovery snapshot untouched; it is
reported through the existing activity/diagnostic path and remains retryable.

## Safe snapshot rotation

The existing `snapshot.json` remains the latest slot for scanner compatibility.
Older slots are `snapshot.previous.json` and `snapshot.older.json`.

Publication order is intentionally constrained:

1. serialize the new payload to a same-directory temporary file;
2. flush, close, fsync, and validate the temporary payload;
3. publish the prior previous slot to older, if present;
4. publish/copy the prior latest slot to previous, if present;
5. atomically replace the temporary file into `snapshot.json` as the final
   publication step.

The current valid `snapshot.json` is never moved or removed before step 5.
Failure injection is required while writing temp, creating older, publishing
previous, immediately before latest publication, and publishing latest. Each
failure must leave the prior `snapshot.json` readable. Rotation is performed
only after the new temporary snapshot is complete.

The current recovery implementation updates `manifest.json` with
`edit_revision`, `snapshot_revision`, and `last_snapshot_at` on each write, and
the scanner validates those values against `snapshot.json`. Feature 33 keeps
that compatibility contract. The snapshot publish and manifest update are
performed with rollback of the complete prior slot set if manifest publication
fails; the prior `snapshot.json` must remain readable. Scanner behavior for a
manually inconsistent manifest/snapshot pair remains deterministic and is
covered by tests. Any per-snapshot metadata added to the snapshot is additive
and does not create a second revision authority.

## Dirty-state and manual-save contract

Autosave calls neither `ProjectService.save_project()` nor any explicit-save
method. A successful autosave may update only recovery snapshot bookkeeping
such as `snapshot_revision`; `RevisionTracker.is_dirty`,
`last_saved_revision`, and manual-save semantics remain unchanged.

The canonical project file, draft artifact, and exported subtitle files are
never autosave targets.

## Test-first plan

Tests use isolated temporary directories and a fake clock/scheduler or direct
timer callback seams; they never wait 30 or 120 real seconds.

Required contracts are AS01–AS19 from the Feature 33 directive. The
merge-blocking safety subset is:

- AS05: successful autosave leaves the tracker dirty;
- AS09: any failed write/rotation preserves the previous latest snapshot;
- AS11: Project A's callback cannot write Project B state;
- AS13: successful manual save cancels pending autosave;
- AS19: one revision is not snapshotted twice;
- max-120s: continuous edits cannot postpone the original max-age deadline.

Additional tests cover clean projects, debounce, rotation, metadata,
unload/dispose, separate identities, activity-log SSOT, and read-only UI
actions. Existing recovery, persistence, revision, and Feature 31 tests must
remain green.

## Explicit omissions

- No Recovery Center UI or restore controls.
- No migration of subtitle ownership into `ProjectState`.
- No change to manual save or recovery restore semantics.
- No background thread without measured evidence of a user-visible freeze.
