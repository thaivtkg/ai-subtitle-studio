# Help Center Guided Tour C1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the local Help Center presentation, controller, search debounce, runtime shortcut view, and route-6 integration required by TC174–TC177.

**Architecture:** Keep guide-card policy pure Python and consume immutable `TourDefinition`/`GuideProgress` snapshots. Keep Qt behavior in `core/help` controllers and `ui/help`, with `MainWindow` limited to composition and navigation wiring.

**Tech Stack:** Python stdlib `unittest`, existing PySide6 UI, existing `AnimatedStack`/navigation adapter.

**Spec:** `docs/superpowers/specs/2026-09-04-help-center-guided-tour-design.md`

## Global Constraints

- Work only in `D:\Temp\Translator` on `codex/help-center-guided-tour-c1`.
- Preserve `core/tutorial/*`; C1.1 policy must not import Qt, `TourProgressStore`, or `TourEngine`.
- Use TDD: write a failing test, run it, then add the minimum implementation.
- Search is local/offline with a 175 ms debounce.
- Runtime shortcut display reads live `QShortcut`/provider state; do not duplicate shortcut strings in documentation.
- Commit and push each task separately.

### Task 1: Verify C1.1 guide-card policy

**Files:**
- Existing: `core/help/__init__.py`
- Existing: `core/help/help_models.py`
- Existing: `core/help/guide_card_policy.py`
- Existing: `tests/test_help_center_c1.py`

**Interfaces:** `build_guide_card_view_model(guide, progress)` returns immutable metadata plus `GuideStartResult` for all six progress statuses.

- [ ] Run targeted C1.1 tests with bundled Python.
- [ ] Run compileall with a writable `PYTHONPYCACHEPREFIX` and `git diff --check`.
- [ ] Commit only if C1.1 needs correction; otherwise retain baseline commit `310094e`.

### Task 2: HelpCenterController

**Files:**
- Create: `core/help/help_center_controller.py`
- Test: `tests/test_help_center_c1.py`

**Interfaces:**
- Consumes: a guide sequence, a progress provider, and a callback for starting a guide.
- Produces: `HelpCenterController.guides`, `search(query)`, `refresh()`, and `start_guide(guide_id)` without mutating project state.

- [ ] Add failing tests for guide listing, local case-insensitive title/description search, unknown guide IDs, and callback routing.
- [ ] Run `python -m unittest tests.test_help_center_c1 -v`; expect missing controller failure.
- [ ] Implement the smallest pure/controller logic using existing guide and progress snapshots.
- [ ] Re-run targeted tests and compileall.
- [ ] Commit `feat(help): add help center controller` and push.

### Task 3: Search debounce

**Files:**
- Modify: `core/help/help_center_controller.py`
- Test: `tests/test_help_center_c1.py`

**Interfaces:** `HelpCenterController.schedule_search(query)` emits/applies only the latest query after `SEARCH_DEBOUNCE_MS = 175`.

- [ ] Add a deterministic test using an injected scheduling callback/clock boundary; verify an older query cannot publish after a newer query.
- [ ] Run targeted test and confirm RED.
- [ ] Add only the 175 ms debounce state needed by the existing controller; do not add a search engine.
- [ ] Run targeted tests, compileall, and diff-check.
- [ ] Commit `feat(help): debounce help search` and push.

### Task 4: Runtime shortcut provider/view

**Files:**
- Create: `core/help/shortcut_provider.py`
- Create: `ui/help/shortcut_view.py`
- Test: `tests/test_help_center_c1.py`

**Interfaces:** Provider returns current shortcut entries from registered runtime shortcuts; view renders provider entries and has no editable-shortcut behavior.

- [ ] Add failing tests for live shortcut extraction, stable ordering, and refresh after provider changes.
- [ ] Run targeted test and confirm RED.
- [ ] Implement a thin provider adapter over existing `QShortcut` objects and a minimal Qt view.
- [ ] Run targeted Qt tests where PySide6 is available; otherwise record the environment limitation.
- [ ] Commit `feat(help): expose runtime shortcuts` and push.

### Task 5: Help page, sidebar, F1, and route 6

**Files:**
- Create: `ui/pages/help_center_page.py`
- Modify: `ui/Gui.py`
- Modify: `tests/test_help_center_c1.py`

**Interfaces:** Help page is an application page in route `help`/index 6; sidebar action and F1 navigate there without starting a tour automatically.

- [ ] Add failing integration tests for route 6, sidebar navigation, and F1 behavior.
- [ ] Run the focused test and confirm RED.
- [ ] Add the smallest page/composition wiring while preserving existing project actions and shortcuts.
- [ ] Run focused tests, compileall, and diff-check.
- [ ] Commit `feat(help): add help center page and entry points` and push.

### Task 6: C1 regression gate

**Files:**
- Modify only files required by failing C1 tests.

- [ ] Run targeted C1 tests with the exact discovery pattern.
- [ ] Run full discovery: `python -m unittest discover -s tests -p "test*.py"`.
- [ ] Run compileall and `git diff --check`.
- [ ] Review `git diff HEAD~1`, confirm no `core/tutorial/*` regression or unrelated refactor.
- [ ] Push the final C1 branch state and report Qt/PySide6 runtime limitations separately.
