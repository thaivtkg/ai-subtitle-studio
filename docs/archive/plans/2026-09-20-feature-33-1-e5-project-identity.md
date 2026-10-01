# Feature 33.1 E.5 Project Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve the exact project identity bound to each Queue item so Queue navigation never substitutes a different project that happens to use the same video.

**Architecture:** Queue metadata will carry optional `project_id` and `project_root` bindings. Resolution will prefer those bindings, then the legacy in-memory directory map, and only then allow the existing unbound auto-create fallback. Canonical artifact ownership and lifecycle flush remain unchanged; project transition will still flush the currently active project before opening the bound destination.

**Tech Stack:** Python, PySide6, existing `QueueManager`, `QueueWidget`, `ProjectService`, `WorkspaceService`, unittest.

**Spec:** Feature 33.1 E.5 — Fix Project Identity / Queue Project Mapping (user-provided request).

## Global Constraints

- `video_path` is not a project identity.
- Explicit Queue `project_id`/`project_root` always wins over video-based discovery.
- Auto-create is allowed only for genuinely unbound Queue items and must bind the created project back to that item.
- Project-owned canonical artifacts under `<project-root>/artifacts/timing` remain unchanged.
- Do not merge PR #33, start MA3, change the 1000 ms timer, or redesign project persistence.
- Do not amend prior commits; create a new E.5 commit only after RED/GREEN verification.

## Review Focus

- Same source video bound to two project roots must resolve to the selected binding; test in `tests/test_queue_project_identity.py`.
- A Queue-created raw video must be auto-created once and reused; test in `tests/test_queue_project_identity.py`.
- Workspace restore must bind the loaded project before Queue activation; test in `tests/test_queue_project_identity.py`.
- The real A→B→Queue(A) path must persist A's project-owned artifact and cold-load it; extend `tests/test_project_switch_real_editor_persistence.py`.
- Legacy video-only entries must not silently override an explicit current project binding; test the fallback policy in `tests/test_queue_project_identity.py`.

---

### Task 1: Lock queue identity behavior with failing tests

**Files:**
- Create: `tests/test_queue_project_identity.py`
- Modify: `tests/test_project_switch_real_editor_persistence.py`

**Interfaces:**
- Tests will exercise `QueueManager.add_video(..., project_id=..., project_root=...)`, `QueueManager.bind_project(...)`, and `MainWindow.on_queue_item_clicked(..., project_root=..., project_id=...)` only if those parameters are needed by the minimal implementation.

- [ ] **Step 1: Add tests for explicit binding, same-video isolation, one-time unbound auto-create, and workspace binding.**
- [ ] **Step 2: Run only the new tests and confirm they fail because Queue has no explicit project binding/resolution.**

### Task 2: Add minimal Queue binding metadata

**Files:**
- Modify: `core/queue_manager.py`
- Modify: `ui/queue_widget.py` and `ui/queue_item.py` only if the existing click payload must carry a stable bound item key.

**Interfaces:**
- `QueueManager.add_video(vid_path, project_id=None, project_root=None)` preserves the old call form.
- `QueueManager.bind_project(vid_path, project_id=None, project_root=None)` stores explicit ownership on the Queue item.
- Existing video-path callers continue to work unchanged.

- [ ] **Step 1: Implement optional binding fields without changing canonical artifact behavior.**
- [ ] **Step 2: Run queue identity tests and verify metadata is retained after repeated clicks/sync.**

### Task 3: Centralize project resolution in MainWindow

**Files:**
- Modify: `ui/Gui.py`
- Modify: `core/services/project_service.py` only if a small exact-project helper is required.
- Modify: `core/services/workspace_service.py`

**Interfaces:**
- `MainWindow.on_queue_item_clicked()` resolves explicit Queue `project_id`/`project_root` before legacy `_queue_project_dirs` and before video-name auto-create.
- A created project is immediately bound back to the originating Queue item.
- `WorkspaceService.restore_workspace()` passes the loaded project identity when activating its source video.

- [ ] **Step 1: Write the smallest resolution helper around existing project open/create methods.**
- [ ] **Step 2: Route explicit project open, workspace restore, Queue auto-create, and normal Queue clicks through that helper.**
- [ ] **Step 3: Preserve transition flush ordering and existing unbound-video behavior.**

### Task 4: Prove cold-load MA2 durability and regression safety

**Files:**
- Modify: `tests/test_project_switch_real_editor_persistence.py`
- Modify: `tests/test_queue_project_identity.py` if shared helpers are needed.

- [ ] **Step 1: Add a real project A/project B Queue flow with a shared source-video case and persisted artifact assertions.**
- [ ] **Step 2: Destroy the in-memory service/model and reopen A from its project root; assert the token and manifest remain in A only.**
- [ ] **Step 3: Run the E.5 tests, E.1/E.2/E.3 regressions, canonical/C3/recovery suites, and relevant persistence tests.**

### Task 5: Verify, commit, push, and prepare a fresh build

**Files:**
- No additional source files unless verification exposes a real regression.

- [ ] **Step 1: Run compile checks and `git diff --check`.**
- [ ] **Step 2: Commit a new precise E.5 fix without amending prior commits.**
- [ ] **Step 3: Push `feature/canonical-autosave`, verify remote HEAD and CI on the new SHA.**
- [ ] **Step 4: Build into a new generated directory and record the exact executable path/SHA256 for one final MA2-A retest.**
