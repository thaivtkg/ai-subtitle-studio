# Feature 33 — Project Autosave Infrastructure

**Status:** Amended design for review
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
  - generation + active session identity guard
        ↓
MainWindow.capture_recovery_working_state()
        ↓
RecoveryManager.write_snapshot()
        ↓
AtomicSnapshotStore
  manifest.json          + snapshot.json          current
  manifest.previous.json + snapshot.previous.json previous
  manifest.older.json    + snapshot.older.json    older
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
4. after success, wait for a newer revision before starting another cycle;
5. after a failed attempt, retry after 30 seconds only while the same
   generation/session is current, the tracker remains dirty, and
   `edit_revision > snapshot_revision`.

The max-age timer is never restarted by later edits. A clean project never
gets an autosave. Repeated callbacks for the same revision do not write again.
Failure retry is bounded by the same 30-second delay, never a busy loop. A
new edit may restart the normal inactivity timer, but does not reset the
original max-age deadline.

## Identity and lifecycle safety

Each scheduled callback captures a monotonically increasing generation and the
currently active `RecoverySession.session_id`. This pair is the primary
runtime token. Existing project id, project path, source path and source
fingerprint remain validation metadata, not a competing identity authority.

The callback must verify generation and session before capture, capture a
deep-copied working snapshot, then verify generation and session again before
persistence and target that exact active session. A source switch, unload,
clear, new project, or shutdown increments the generation and cancels both
timers. A callback from Project A therefore cannot publish Project B data into
A's recovery session, including when the callback is invalidated during
capture.

Manual save success cancels the pending cycle but leaves existing recovery
cleanup behavior unchanged. Autosave failure leaves editing, dirty state,
saved-revision state, and the last valid recovery snapshot untouched; it is
reported through the existing activity/diagnostic path and retries after 30
seconds only when the generation/session and dirty/new-revision checks still
pass.

## Safe paired-slot rotation and scanner fallback

Recovery slots are complete pairs:

```text
manifest.json          + snapshot.json          current
manifest.previous.json + snapshot.previous.json previous
manifest.older.json    + snapshot.older.json    older
```

A slot is valid only when both files exist and `RecoveryValidator` accepts
them together, including matching session and revision metadata. Two
`os.replace` operations are not treated as one atomic transaction.

The current valid pair must remain discoverable until the new snapshot is
fully written, closed, fsynced, and validated. Rotation prepares/publishes
the previous pair to the older pair, then preserves the current pair as the
previous pair, and publishes the new current pair last. The implementation
must never move or remove the current `snapshot.json` before the final latest
snapshot publication. Equivalent temporary-file/copy steps are allowed only
if they preserve at least one complete valid pair at every failure point.

Failure injection is mandatory for temporary snapshot creation/write,
temporary manifest creation/write, previous-to-older preparation,
current-to-previous preservation, immediately before current snapshot
publication, current snapshot publication, and current manifest publication.
At every injected failure, the old complete recovery pair remains readable
and discoverable. A failure must not leave only an unpaired current file as
the sole recovery option.

The current recovery implementation updates `manifest.json` with
`edit_revision`, `snapshot_revision`, and `last_snapshot_at` on each write,
and the scanner validates those values against `snapshot.json`. Feature 33
keeps that compatibility contract by rotating manifests and snapshots as
pairs. If a crash leaves the current pair inconsistent, scanning tries the
current pair, then the previous pair, then the older pair. Only when no pair
is valid does the existing quarantine/reject policy apply.

Crash-consistency tests must cover:

- CRASH-C01: new snapshot published, old manifest remains → previous pair;
- CRASH-C02: new manifest published, current snapshot mismatched → previous
  pair;
- CRASH-C03: current pair corrupt, previous pair valid → previous candidate;
- CRASH-C04: all pairs invalid → existing quarantine policy.

Any per-snapshot metadata added to a snapshot is additive and does not create
a second revision authority.

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

Required contracts are AS01–AS24 from the Feature 33 directive. The
merge-blocking safety subset is:

- AS05: successful autosave leaves the tracker dirty;
- AS09: any failed write/rotation preserves the previous latest snapshot;
- AS11: Project A's callback cannot write Project B state;
- AS13: successful manual save cancels pending autosave;
- AS19: one revision is not snapshotted twice;
- AS20: failed autosave retries after 30 seconds without advancing revision;
- AS21: successful explicit save clears obsolete recovery history;
- AS22: clean-point invalidation clears all rotated recovery slots;
- AS23: discard removes all rotated slot files and the session directory;
- AS24: clean shutdown leaves no orphan rotated recovery files;
- max-120s: continuous edits cannot postpone the original max-age deadline.

Additional tests cover clean projects, debounce, paired-slot crash fallback,
metadata, unload/dispose, separate identities, activity-log SSOT, and
read-only UI actions. Existing recovery, persistence, revision, and Feature 31
tests must remain green.

`RevisionTracker.snapshot_revision` remains the durable recovery progress
source of truth. A coordinator cache may exist only as an ephemeral callback
deduplication optimization; it must never replace or diverge from the tracker
value.

History cleanup is explicit: successful manual save, clean-point
invalidation, discard, clean shutdown, and old-session switch remove or
invalidate all current/previous/older manifest+snapshot pairs according to
the existing recovery lifecycle. No rotated slot may prevent session cleanup.

## Explicit omissions

- No Recovery Center UI or restore controls.
- No migration of subtitle ownership into `ProjectState`.
- No change to manual save or recovery restore semantics.
- No background thread without measured evidence of a user-visible freeze.
