# Help Center + Interactive Guided Tour — Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every production change follows RED → GREEN → REFACTOR.

**Goal:** Build the UI-independent tutorial contracts, validated local scenario catalog, deterministic TourEngine state machine, and crash-safe user progress persistence required before any concrete Spotlight/Dialog/Help Center UI integration.

**Architecture:** Milestone A lives under `core/tutorial/` and uses immutable dataclasses plus semantic ports. `TourEngine(QObject)` may import only QtCore primitives and talks to fakeable ports; concrete QWidget/QDialog implementations are deferred to Milestone B. `TourProgressStore` persists user learning state independently from Project/Recovery using same-directory temp files, `fsync`, and `os.replace`.

**Tech Stack:** Python 3.10+, PySide6 QtCore only for `TourEngine`, standard-library `json`, `dataclasses`, `enum`, `pathlib`, `os`, `uuid`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-04-help-center-guided-tour-design.md`

## Global Constraints

- `TourEngine` may import `PySide6.QtCore` only; no `PySide6.QtWidgets` or `PySide6.QtGui` under `core/tutorial/tour_engine.py`.
- Scenario data is declarative only: no executable callbacks, raw Qt signal names, Python expressions, page indices, tab indices, or pixel coordinates.
- Step types v1 are exactly `INFO`, `ACTION`, `DEMO`.
- Interaction kinds v1 are exactly `CLICK`, `FOCUS`, `TEXT_COMMITTED`, `SELECTION_CHANGED`, `DIALOG_ACCEPTED`.
- Callout placement v1 is exactly `auto`, `top`, `bottom`, `left`, `right`, `center`.
- Missing-anchor policies are exactly `REQUIRED`, `FALLBACK_TO_INFO`, `SKIP`; default is `FALLBACK_TO_INFO`.
- `ACTION.allow_back` defaults to `false`; `INFO` and `DEMO` default to `true`; `FOCUS` may explicitly opt into Back.
- `surface` is optional and inherits the current surface when omitted.
- Tutorial assets must resolve under `resources/tutorials/`; path traversal is rejected.
- `NAVIGATION_TIMEOUT_MS = 2500`; `TARGET_SETTLE_TIMEOUT_MS = 750`; both must be injectable for tests.
- ACTION acknowledgement is synchronous, but next-step preparation is queued with `QTimer.singleShot(0, ...)`.
- Every async callback is guarded by `tour_session_id` + `step_generation`; navigation callbacks also validate `navigation_request_id`.
- `cleanup_step_scope()` and observer cleanup calls must be idempotent.
- Tour cancellation never rolls back business state.
- `tutorial_progress.json` is user-level state only; it must never dirty `ProjectState`, `RevisionTracker`, or `RecoveryManager`.
- Progress writes use same-directory temp → flush → `os.fsync` → close → `os.replace`.
- Future progress `schema_version` is read-only and must never be downgraded or overwritten.
- Corrupt progress is quarantined when possible; startup continues with empty progress. If quarantine fails, persistence becomes read-only and the corrupt file is preserved.
- Tests use `unittest`, matching the repository's existing suite.
- Final Milestone A gate:

```bash
python -m unittest tests.test_tour_catalog tests.test_tour_engine tests.test_tour_progress_store -v
python -m unittest discover -s tests -v
python -m compileall core tests main.py
git diff --check
```

---

# Milestone Mapping

The acceptance IDs are traceability identifiers, not implementation order. The original contiguous-range proposal would place `TourProgressStore` outside Milestone A and concrete UI adapters inside it. Use responsibility-based ownership instead:

```text
Milestone A — Core Contracts / Engine / Persistence
TC132–TC138
TC145–TC147
TC152–TC157
TC166–TC173

Milestone B — Concrete Qt UI Adapters / Modal / Spotlight
TC139–TC144
TC148–TC151
TC158–TC165

Milestone C — Help Center / First Run / Demo
TC174–TC185

Milestone D — Packaging / E2E / Final Verification
TC186–TC193
```

Every TC132–TC193 belongs to exactly one milestone.

---

# Milestone A File Map

```text
core/tutorial/
├─ __init__.py
├─ models.py          # frozen enums/dataclasses shared by catalog + engine
├─ catalog.py         # JSON parsing, validation, resource confinement, fault isolation
├─ ports.py           # UI-independent Protocol contracts used by TourEngine
├─ environment.py     # semantic read-only precondition evaluation contract
├─ tour_engine.py     # QtCore-only state machine and async guards
└─ progress_store.py  # atomic user progress persistence/version semantics

core/runtime/runtime_paths.py
    + get_tutorial_progress_file()

resources/tutorials/
├─ catalog.json       # local list of guide files
└─ getting_started.json  # minimal valid fixture/seed guide, no production-heavy action

tests/
├─ test_tour_catalog.py
├─ test_tour_engine.py
└─ test_tour_progress_store.py
```

Milestone A must not create `ui/tutorial/` yet.

---

## Task A1: Immutable Tour Models + Base Scenario Parser

**Acceptance:** TC132, TC133, TC134, TC135

**Files:**
- Create: `core/tutorial/__init__.py`
- Create: `core/tutorial/models.py`
- Create: `core/tutorial/catalog.py`
- Create: `tests/test_tour_catalog.py`

**Interfaces:**
- Produces enums: `TourStepType`, `InteractionKind`, `TargetPolicy`, `CalloutPlacement`, `TourState`.
- Produces frozen dataclasses: `SurfaceSpec`, `CalloutSpec`, `InteractionSpec`, `DemoSpec`, `SafetySpec`, `TourStep`, `TourDefinition`.
- Produces: `parse_tour_definition(payload: Mapping[str, object]) -> TourDefinition`.
- Later tasks rely on `TourStep.surface: SurfaceSpec | None` and normalized `SafetySpec.allow_back`.

### RED

- [ ] **Step 1: Write TC132 immutable parse test**

In `tests/test_tour_catalog.py`:

```python
import unittest
from dataclasses import FrozenInstanceError

from core.tutorial.catalog import parse_tour_definition
from core.tutorial.models import TourStepType


class TestTourDefinitionParsing(unittest.TestCase):
    def _valid_payload(self):
        return {
            "schema_version": 1,
            "guide_id": "getting_started",
            "content_version": 1,
            "title": "Getting Started",
            "description": "Learn the basic workflow.",
            "category": "getting_started",
            "estimated_minutes": 3,
            "steps": [
                {
                    "step_id": "intro",
                    "type": "INFO",
                    "surface": {"route": "dashboard"},
                    "callout": {
                        "title": "Welcome",
                        "body": "This is the dashboard.",
                        "placement": "auto",
                    },
                }
            ],
        }

    def test_tc132_parse_returns_frozen_definition(self):
        definition = parse_tour_definition(self._valid_payload())
        self.assertEqual(definition.guide_id, "getting_started")
        self.assertEqual(definition.steps[0].step_type, TourStepType.INFO)
        with self.assertRaises(FrozenInstanceError):
            definition.guide_id = "mutated"
```

- [ ] **Step 2: Write TC133 surface inheritance representation test**

```python
    def test_tc133_missing_surface_is_none_for_engine_inheritance(self):
        payload = self._valid_payload()
        payload["steps"].append({
            "step_id": "same_surface",
            "type": "INFO",
            "callout": {
                "title": "Continue",
                "body": "Stay on the current surface.",
                "placement": "bottom",
            },
        })
        definition = parse_tour_definition(payload)
        self.assertIsNone(definition.steps[1].surface)
```

- [ ] **Step 3: Write TC134 Back default tests**

```python
    def test_tc134_back_defaults_follow_step_type(self):
        payload = self._valid_payload()
        payload["steps"] = [
            {
                "step_id": "info",
                "type": "INFO",
                "callout": {"title": "I", "body": "I", "placement": "auto"},
            },
            {
                "step_id": "action",
                "type": "ACTION",
                "anchor": "demo.button",
                "interaction": {"kind": "CLICK"},
                "callout": {"title": "A", "body": "A", "placement": "auto"},
            },
            {
                "step_id": "demo",
                "type": "DEMO",
                "demo": {"asset": "assets/demo.gif", "media_type": "ANIMATED_IMAGE", "fit": "contain"},
                "callout": {"title": "D", "body": "D", "placement": "center"},
            },
        ]
        definition = parse_tour_definition(payload)
        self.assertTrue(definition.steps[0].safety.allow_back)
        self.assertFalse(definition.steps[1].safety.allow_back)
        self.assertTrue(definition.steps[2].safety.allow_back)
```

- [ ] **Step 4: Write TC135 placement enum rejection test**

```python
    def test_tc135_unknown_callout_placement_is_rejected(self):
        payload = self._valid_payload()
        payload["steps"][0]["callout"]["placement"] = "floating-anywhere"
        with self.assertRaises(ValueError):
            parse_tour_definition(payload)
```

- [ ] **Step 5: Run RED**

```bash
python -m unittest tests.test_tour_catalog.TestTourDefinitionParsing -v
```

Expected: FAIL because `core.tutorial` models/parser do not exist.

### GREEN

- [ ] **Step 6: Create frozen enums/dataclasses in `core/tutorial/models.py`**

Use exact enum values from the spec:

```python
from dataclasses import dataclass, field
from enum import Enum


class TourStepType(str, Enum):
    INFO = "INFO"
    ACTION = "ACTION"
    DEMO = "DEMO"


class InteractionKind(str, Enum):
    CLICK = "CLICK"
    FOCUS = "FOCUS"
    TEXT_COMMITTED = "TEXT_COMMITTED"
    SELECTION_CHANGED = "SELECTION_CHANGED"
    DIALOG_ACCEPTED = "DIALOG_ACCEPTED"


class TargetPolicy(str, Enum):
    REQUIRED = "REQUIRED"
    FALLBACK_TO_INFO = "FALLBACK_TO_INFO"
    SKIP = "SKIP"


class CalloutPlacement(str, Enum):
    AUTO = "auto"
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


class TourState(str, Enum):
    IDLE = "IDLE"
    PREPARING_SURFACE = "PREPARING_SURFACE"
    RESOLVING_TARGET = "RESOLVING_TARGET"
    SHOWING_INFO = "SHOWING_INFO"
    WAITING_ACTION = "WAITING_ACTION"
    SHOWING_DEMO = "SHOWING_DEMO"
    ADVANCING_STEP = "ADVANCING_STEP"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
```

Define all scenario dataclasses with `@dataclass(frozen=True)` and store `TourDefinition.steps` as `tuple[TourStep, ...]`, never mutable `list`.

- [ ] **Step 7: Implement minimal `parse_tour_definition()`**

Requirements for this task only:

```text
- convert strings to enums;
- surface omitted → None;
- target_policy omitted → FALLBACK_TO_INFO;
- safety.allow_skip_step and allow_skip_tour default True;
- safety.allow_back default by step type;
- reject invalid enum values via ValueError;
- return tuple steps.
```

Do not add filesystem access yet; Task A2 owns confinement/catalog loading.

- [ ] **Step 8: Run GREEN**

```bash
python -m unittest tests.test_tour_catalog.TestTourDefinitionParsing -v
```

Expected: PASS.

### REFACTOR

- [ ] **Step 9: Extract small private parsing helpers**

Keep helpers focused, e.g. `_parse_surface`, `_parse_callout`, `_parse_safety`, `_parse_step`. Do not create a generic reflection-based deserializer.

- [ ] **Step 10: Re-run tests and commit**

```bash
python -m unittest tests.test_tour_catalog.TestTourDefinitionParsing -v
git add core/tutorial tests/test_tour_catalog.py
git commit -m "feat: add immutable guided tour scenario models"
```

---

## Task A2: Strict Scenario Validation, Asset Confinement, and Catalog Fault Isolation

**Acceptance:** TC136, TC137, TC138

**Files:**
- Modify: `core/tutorial/catalog.py`
- Create: `resources/tutorials/catalog.json`
- Create: `resources/tutorials/getting_started.json`
- Modify: `tests/test_tour_catalog.py`

**Interfaces:**
- Produces: `class TourCatalog`.
- Constructor: `TourCatalog(tutorial_root: Path)`.
- `load_guide(relative_path: str) -> TourDefinition`.
- `load_all() -> tuple[TourDefinition, ...]`.
- Catalog file v1 implementation detail:

```json
{
  "schema_version": 1,
  "guides": ["getting_started.json"]
}
```

### RED

- [ ] **Step 1: Write TC136 forbidden-field tests**

```python
class TestTourCatalogValidation(unittest.TestCase):
    def test_tc136_executable_and_raw_signal_fields_are_rejected(self):
        forbidden = [
            ("execute", "project_service.create_project()"),
            ("callback", "MainWindow._on_new_from_url"),
            ("signal", "clicked"),
            ("page_index", 1),
            ("tab_index", 2),
        ]
        for key, value in forbidden:
            payload = self._valid_payload()
            payload["steps"][0][key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    parse_tour_definition(payload)
```

- [ ] **Step 2: Write TC137 traversal test using a temporary tutorial root**

Create a guide with DEMO asset `../outside.gif` and assert `TourCatalog.load_guide()` raises `ValueError` before opening the outside file.

- [ ] **Step 3: Write TC138 mixed valid/invalid catalog test**

Create `catalog.json` with `valid.json` and `invalid.json`; assert `load_all()` returns only the valid guide and exposes diagnostics via a read-only `errors` tuple/list property without throwing away the valid result.

- [ ] **Step 4: Run RED**

```bash
python -m unittest tests.test_tour_catalog.TestTourCatalogValidation -v
```

Expected: FAIL because strict validation/catalog loading is not implemented.

### GREEN

- [ ] **Step 5: Add strict allowed-key validation**

Use explicit allowlists per object shape. Reject unknown executable-looking or implementation-specific fields rather than silently ignoring them.

Required guide keys:

```text
schema_version, guide_id, content_version, title, description,
category, estimated_minutes, steps
```

Required/allowed step keys:

```text
step_id, type, surface, anchor, target_policy, callout,
interaction, demo, preconditions, safety
```

Rules:

```text
ACTION requires anchor + interaction.
DEMO requires demo.
INFO must not contain interaction.
steps must be non-empty.
step_id unique within guide.
schema_version must equal 1.
```

- [ ] **Step 6: Implement safe path resolution**

Resolve with:

```python
root = tutorial_root.resolve()
candidate = (root / relative_path).resolve()
if candidate != root and root not in candidate.parents:
    raise ValueError("Tutorial path escapes resource root")
```

Apply the same rule to DEMO assets. Do not rely only on string-prefix checks.

- [ ] **Step 7: Implement `TourCatalog.load_all()` fault isolation**

Load `catalog.json`, iterate each listed relative guide path independently, collect valid definitions, collect validation/read errors as diagnostics, and continue. Duplicate `guide_id` across valid files makes the later conflicting guide invalid rather than replacing the earlier one silently.

- [ ] **Step 8: Add minimal packaged source resources**

`resources/tutorials/getting_started.json` must be a lightweight INFO-only guide so Milestone A does not create UI/business side effects.

- [ ] **Step 9: Run GREEN**

```bash
python -m unittest tests.test_tour_catalog -v
```

Expected: TC132–TC138 PASS.

### REFACTOR

- [ ] **Step 10: Keep parser and filesystem responsibilities separate**

`parse_tour_definition()` validates structure; `TourCatalog` owns file/path operations. Do not move filesystem calls into dataclasses.

- [ ] **Step 11: Commit**

```bash
git add core/tutorial/catalog.py resources/tutorials tests/test_tour_catalog.py
git commit -m "feat: validate and isolate guided tour scenarios"
```

---

## Task A3: Core Ports, Opaque Handles, and Read-Only TourEnvironment

**Acceptance support:** prerequisites for TC145–TC157; no new acceptance ID is invented.

**Files:**
- Modify: `core/tutorial/models.py`
- Create: `core/tutorial/ports.py`
- Create: `core/tutorial/environment.py`
- Create: `tests/test_tour_engine.py`

**Interfaces:**
- Produces `AnchorStatus`, `AnchorHandle`, `AnchorResolution` as UI-opaque frozen models.
- Produces Protocols: `NavigationPort`, `AnchorRegistryPort`, `InteractionObserverPort`, `SpotlightPort`, `DialogObserverPort`, `ProgressStorePort`.
- Produces `TourEnvironment(checker: Callable[[str], bool])` and `check(precondition: str) -> bool`.
- No port may require importing QtWidgets/QtGui.

### RED

- [ ] **Step 1: Write opaque-handle test**

```python
from core.tutorial.models import AnchorHandle, AnchorResolution, AnchorStatus


def test_anchor_handle_contains_no_widget_contract(self):
    handle = AnchorHandle(
        anchor_id="media.new_from_url",
        host_id="main-window",
        resolution_generation=1,
    )
    self.assertFalse(hasattr(handle, "widget"))
```

Use `unittest.TestCase` syntax in the real file.

- [ ] **Step 2: Write environment read-only semantic test**

```python
def test_environment_delegates_semantic_precondition_without_mutation(self):
    seen = []
    env = TourEnvironment(lambda key: seen.append(key) or key == "PROJECT_OPEN")
    self.assertTrue(env.check("PROJECT_OPEN"))
    self.assertEqual(seen, ["PROJECT_OPEN"])
```

- [ ] **Step 3: Run RED**

```bash
python -m unittest tests.test_tour_engine -v
```

Expected: FAIL because ports/handles/environment do not exist.

### GREEN

- [ ] **Step 4: Add opaque anchor models**

```python
class AnchorStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"
    NOT_VISIBLE = "NOT_VISIBLE"


@dataclass(frozen=True)
class AnchorHandle:
    anchor_id: str
    host_id: str
    resolution_generation: int


@dataclass(frozen=True)
class AnchorResolution:
    status: AnchorStatus
    handle: AnchorHandle | None = None
    reason: str | None = None
```

Do not add QWidget, QPoint, QRect, QDialog, or QObject references.

- [ ] **Step 5: Define minimal Protocol contracts in `ports.py`**

Protocols define only methods TourEngine calls; concrete Qt signal objects remain runtime attributes on implementations/fakes and are not modeled as widget types. Include:

```python
class NavigationPort(Protocol):
    def navigate(self, surface: SurfaceSpec, *, session_id: str, generation: int, request_id: str) -> None: ...
    def cancel_pending(self) -> None: ...

class AnchorRegistryPort(Protocol):
    def resolve(self, anchor_id: str) -> AnchorResolution: ...

class InteractionObserverPort(Protocol):
    def bind(self, anchor: AnchorHandle, interaction: InteractionSpec, *, session_id: str, generation: int): ...
    def unbind(self) -> None: ...

class SpotlightPort(Protocol):
    def hide_step(self) -> None: ...
```

Add only methods actually used by Task A4/A5.

- [ ] **Step 6: Implement `TourEnvironment`**

Keep it read-only: it calls the injected checker and returns `bool`; it does not expose `ensure_*` methods.

- [ ] **Step 7: Run GREEN and commit**

```bash
python -m unittest tests.test_tour_engine -v
git add core/tutorial tests/test_tour_engine.py
git commit -m "feat: define guided tour core ports"
```

---

## Task A4: TourEngine Lifecycle, Missing-Anchor Policy, Back, and Cancel

**Acceptance:** TC147, TC155, TC156, TC157

**Files:**
- Create: `core/tutorial/tour_engine.py`
- Modify: `tests/test_tour_engine.py`

**Interfaces:**
- Produces `TourEngine(QObject)` with public API:

```python
state_changed = Signal(object)
tour_started = Signal(str)
step_changed = Signal(str, str, int, int)
tour_completed = Signal(str)
tour_cancelled = Signal(str, str)

start(guide_id: str) -> bool
next() -> None
back() -> None
skip_step() -> None
retry() -> None
cancel(reason: str = "USER_CANCELLED") -> None
state() -> TourState
current_step() -> TourStep | None
is_running() -> bool
```

- Constructor receives catalog, registry, navigation, observer, spotlight, dialog observer, progress store, environment, plus injectable timeouts.

### RED

- [ ] **Step 1: Build small fake ports inside `tests/test_tour_engine.py`**

Fakes must record calls and expose minimal QtCore `Signal`s where the engine expects asynchronous notifications. Do not import QtWidgets.

- [ ] **Step 2: Write TC147 policy table test**

For an unresolved anchor, assert:

```text
REQUIRED → RECOVERING
FALLBACK_TO_INFO → SHOWING_INFO without target
SKIP → queues/advances to the next step
```

- [ ] **Step 3: Write TC155 Back rebuild test for INFO/DEMO**

Start a two-step guide, move to step 2, call `back()`, then assert step index returns to 0 and the engine re-enters the normal prepare/resolve pipeline rather than restoring stale presentation state.

- [ ] **Step 4: Write TC156 ACTION Back-disabled test**

Start on ACTION with default safety and assert `back()` leaves step/state unchanged.

- [ ] **Step 5: Write TC157 cancel cleanup test**

```python
engine.cancel("USER_CANCELLED")
self.assertEqual(engine.state(), TourState.CANCELLED)
self.assertEqual(observer.unbind_calls, 1)
self.assertEqual(spotlight.hide_calls, 1)
self.assertFalse(engine.is_running())
```

Call cancel a second time and assert cleanup remains safe/idempotent.

- [ ] **Step 6: Run RED**

```bash
python -m unittest tests.test_tour_engine -v
```

Expected: FAIL because `TourEngine` does not exist.

### GREEN

- [ ] **Step 7: Implement QtCore-only `TourEngine` skeleton**

Imports allowed from PySide6:

```python
from PySide6.QtCore import QObject, QTimer, Signal, Slot
```

No QtWidgets/QtGui imports.

- [ ] **Step 8: Implement `start()` and step preparation pipeline**

Required order:

```text
snapshot TourDefinition
new tour_session_id
step_generation = 0
index = 0
start dialog observation
PREPARING_SURFACE
if surface is None → RESOLVING_TARGET
else navigation request
```

Do not resolve anchors before the surface-preparation phase completes.

- [ ] **Step 9: Implement `_resolve_current_target()` target-policy handling**

For INFO without anchor, allow presentation without target. For ACTION, missing target applies target policy. For DEMO, target is optional unless scenario explicitly supplies one.

- [ ] **Step 10: Implement `back()`, `skip_step()`, `retry()`, `cancel()`**

`cancel()` must invalidate the current session before/while cleaning resources so late callbacks become no-ops.

- [ ] **Step 11: Implement one idempotent `_cleanup_step_scope()`**

It calls observer unbind, hides current spotlight/demo presentation through the port, and clears step-scoped bookkeeping. It must be safe when called more than once.

- [ ] **Step 12: Run GREEN**

```bash
python -m unittest tests.test_tour_engine -v
```

Expected: TC147, TC155–TC157 PASS.

### REFACTOR

- [ ] **Step 13: Centralize state assignment**

Use one private `_set_state(new_state)` path that emits `state_changed`; do not scatter direct writes plus duplicate signal emissions.

- [ ] **Step 14: Commit**

```bash
git add core/tutorial/tour_engine.py tests/test_tour_engine.py
git commit -m "feat: add guided tour core state machine"
```

---

## Task A5: Async Session Guards, Queued ACTION Advance, and Navigation Watchdog

**Acceptance:** TC145, TC146, TC152, TC153, TC154

**Files:**
- Modify: `core/tutorial/tour_engine.py`
- Modify: `tests/test_tour_engine.py`

**Interfaces:**
- Adds guarded engine event entry points:

```python
on_surface_ready(session_id: str, generation: int, request_id: str) -> None
on_surface_failed(session_id: str, generation: int, request_id: str, reason: str) -> None
on_action_satisfied(session_id: str, generation: int) -> None
on_target_lost(session_id: str, generation: int, reason: str) -> None
```

- Keeps defaults `NAVIGATION_TIMEOUT_MS = 2500`, `TARGET_SETTLE_TIMEOUT_MS = 750` but constructor accepts overrides.

### RED

- [ ] **Step 1: Write TC145 stale navigation token test**

Capture request 1, advance generation/request to request 2, then deliver `on_surface_ready()` for request 1. Assert state/current step do not change.

- [ ] **Step 2: Write TC146 navigation timeout test with short injected timeout**

Use e.g. 10 ms in the test, run a local `QEventLoop` long enough for timeout, assert:

```text
state == RECOVERING
navigation.cancel_pending called
stale request invalidated
```

Never sleep for 2.5 seconds in unit tests.

- [ ] **Step 3: Write TC152 detach-before-advance ordering test**

Fake observer records `unbind` sequence; fake engine/spotlight records transition events. Assert `unbind` occurs before state leaves `WAITING_ACTION`/before next-step preparation is queued.

- [ ] **Step 4: Write TC153 queued next-step test**

After `on_action_satisfied(...)`, assert immediately that the next step has **not** yet been prepared. Spin one Qt event-loop tick, then assert preparation occurs.

- [ ] **Step 5: Write TC154 late action callback test**

Cancel/skip to increment generation, then deliver old `(session_id, generation)` action callback and assert no state/index mutation.

- [ ] **Step 6: Run RED**

```bash
python -m unittest tests.test_tour_engine -v
```

Expected: new async tests FAIL.

### GREEN

- [ ] **Step 7: Add request/session/generation validation helper**

Use explicit equality checks; do not infer freshness from current state alone.

- [ ] **Step 8: Add navigation watchdog using a single-shot QTimer**

Timer lifecycle:

```text
start when navigation request begins
stop on matching ready/failed
stop during cancellation/cleanup
on timeout → invalidate request → cancel_pending → RECOVERING
```

- [ ] **Step 9: Implement ACTION acknowledgement ordering**

Exact order:

```text
validate session/generation + WAITING_ACTION
observer.unbind()
mark action satisfied / enter ADVANCING_STEP
cleanup remaining step presentation
QTimer.singleShot(0, guarded_prepare_next)
```

The queued closure captures session and the post-advance generation and revalidates both before running.

- [ ] **Step 10: Implement target-settle timer hook without tight polling**

The engine may perform an initial resolve and wait for externally delivered lifecycle/retry triggers until the settle watchdog expires. Do not create a recurring 10 ms poll loop.

- [ ] **Step 11: Run GREEN**

```bash
python -m unittest tests.test_tour_engine -v
```

Expected: TC145–TC147, TC152–TC157 PASS.

### REFACTOR

- [ ] **Step 12: Verify all QTimer callbacks are token-guarded**

Search `core/tutorial/tour_engine.py` for every `singleShot`/timer callback and ensure it captures/validates session + generation; navigation paths also validate request ID.

- [ ] **Step 13: Commit**

```bash
git add core/tutorial/tour_engine.py tests/test_tour_engine.py
git commit -m "feat: harden guided tour async transitions"
```

---

## Task A6: Atomic `TourProgressStore`, Version Semantics, and Corruption Quarantine

**Acceptance:** TC166–TC173

**Files:**
- Modify: `core/runtime/runtime_paths.py`
- Create: `core/tutorial/progress_store.py`
- Create: `tests/test_tour_progress_store.py`

**Interfaces:**
- Add `RuntimePaths.get_tutorial_progress_file() -> Path` returning `<user_data>/tutorial_progress.json` with no mkdir side effect.
- Produces `GuideProgressStatus` runtime enum/status mapping including at least `NOT_STARTED`, `COMPLETED`, `DISMISSED`, `OUTDATED`, `COMPLETED_NEWER_VERSION`, `UNKNOWN`.
- Produces `TourProgressStore(path: Path)` with:

```python
is_completed(guide_id: str, content_version: int) -> bool
mark_completed(guide_id: str, content_version: int) -> bool
mark_dismissed(guide_id: str, content_version: int) -> bool
status(guide_id: str, content_version: int) -> GuideProgress
reset(guide_id: str | None = None) -> bool
```

### RED

- [ ] **Step 1: Write TC166 schema-v1 round-trip test**

Create a temporary path, mark completed/dismissed guides, reconstruct store from disk, and assert canonical statuses/content versions survive.

- [ ] **Step 2: Write TC167 replace-failure preservation test**

Patch `os.replace` to raise `OSError`; assert method reports failure, in-memory snapshot remains old, and canonical bytes remain unchanged.

- [ ] **Step 3: Write TC168 corrupt JSON quarantine test**

Write invalid JSON, construct/read store, assert:

```text
canonical corrupt name no longer used when quarantine succeeds
one tutorial_progress.corrupt.<timestamp>.json exists
store returns empty progress
startup/read does not raise
```

- [ ] **Step 4: Write TC169 quarantine-failure read-only test**

Patch rename/replace used for quarantine to fail; assert corrupt canonical bytes remain untouched and subsequent mutation returns false/does not overwrite the file.

- [ ] **Step 5: Write TC170 future schema test**

Write `schema_version: 99`; assert store becomes read-only unsupported, status returns UNKNOWN where appropriate, and writes do not rewrite schema 99.

- [ ] **Step 6: Write TC171 old-schema migration-in-memory test**

Provide a supported legacy fixture shape (`schema_version: 0`) defined in this task, normalize it in memory, assert file bytes are unchanged immediately after load, then perform an explicit mutation and assert canonical schema 1 is written.

Legacy fixture v0 for this project is intentionally minimal:

```json
{
  "schema_version": 0,
  "completed_guides": {
    "getting_started": 1
  }
}
```

Migration maps each entry to `status=COMPLETED`, same content version; missing timestamp is allowed in the in-memory migrated record until next canonical write.

- [ ] **Step 7: Write TC172 old content version OUTDATED test**

Stored guide v1 completed, current guide v2 → `OUTDATED`, `is_completed(..., 2)` false.

- [ ] **Step 8: Write TC173 newer stored content version test**

Stored v3 completed, current app guide v2 → `COMPLETED_NEWER_VERSION`; calling a read method must not downgrade/write v2.

- [ ] **Step 9: Run RED**

```bash
python -m unittest tests.test_tour_progress_store -v
```

Expected: FAIL because store/getter do not exist.

### GREEN

- [ ] **Step 10: Add RuntimePaths getter**

```python
@staticmethod
def get_tutorial_progress_file() -> Path:
    return RuntimePaths.get_user_data_dir() / "tutorial_progress.json"
```

No directory creation in getter.

- [ ] **Step 11: Implement schema-v1 reader and explicit v0 migration**

Canonical v1:

```json
{
  "schema_version": 1,
  "updated_at": "ISO-8601",
  "guides": {
    "guide_id": {
      "content_version": 1,
      "status": "COMPLETED",
      "completed_at": "ISO-8601"
    }
  }
}
```

Persisted statuses remain only `COMPLETED`/`DISMISSED`.

- [ ] **Step 12: Implement corruption quarantine**

Name format:

```text
tutorial_progress.corrupt.<UTC_TIMESTAMP>.json
```

If quarantine fails, set read-only-corrupt mode and preserve evidence.

- [ ] **Step 13: Implement transactional in-memory update**

```text
old snapshot
→ deep/copy candidate
→ atomic write candidate
→ success: publish candidate
→ failure: keep old snapshot
```

Do not publish completion before disk commit succeeds.

- [ ] **Step 14: Implement same-directory atomic writer**

Temp name:

```text
tutorial_progress.json.tmp.<pid>.<uuid>
```

Algorithm exactly:

```python
with open(temp_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temp_path, canonical_path)
```

Best-effort remove temp on failure; never delete canonical first.

- [ ] **Step 15: Implement version-aware `status()`**

Rules:

```text
same version + COMPLETED → COMPLETED
same version + DISMISSED → DISMISSED
stored older → OUTDATED
stored newer + COMPLETED → COMPLETED_NEWER_VERSION
future progress schema → UNKNOWN/read-only
missing → NOT_STARTED
```

- [ ] **Step 16: Run GREEN**

```bash
python -m unittest tests.test_tour_progress_store -v
```

Expected: TC166–TC173 PASS.

### REFACTOR

- [ ] **Step 17: Separate pure payload normalization from file I/O**

Keep functions such as `_decode_payload`, `_migrate_v0`, `_build_candidate`, `_atomic_write` focused and independently testable. Do not introduce a generic persistence framework.

- [ ] **Step 18: Commit**

```bash
git add core/runtime/runtime_paths.py core/tutorial/progress_store.py tests/test_tour_progress_store.py
git commit -m "feat: persist guided tour progress atomically"
```

---

## Task A7: Milestone A Architecture Guards and Regression Gate

**Acceptance:** closes Milestone A only; no new TC ID.

**Files:**
- Modify if needed: `tests/test_tour_engine.py`
- Modify if needed: `tests/test_tour_catalog.py`
- Modify if needed: `tests/test_tour_progress_store.py`
- No production behavior changes unless a failing test demonstrates a defect.

**Interfaces:** none new.

### RED / Verification Characterization

- [ ] **Step 1: Add architecture import guard test**

Use source inspection/import AST to assert `core/tutorial/tour_engine.py` does not import:

```text
PySide6.QtWidgets
PySide6.QtGui
core.services.project_service
workers
core.media_import
core.subtitle_generation
```

This test protects the approved dependency boundary.

- [ ] **Step 2: Add acceptance-ID presence audit**

Ensure test names/comments make these IDs searchable:

```text
TC132–TC138
TC145–TC147
TC152–TC157
TC166–TC173
```

Do not create fake empty tests just to satisfy the audit; each ID must be attached to a real assertion.

### GREEN / Final Verification

- [ ] **Step 3: Run Milestone A focused suite**

```bash
python -m unittest tests.test_tour_catalog tests.test_tour_engine tests.test_tour_progress_store -v
```

Expected: all Milestone A tests pass.

- [ ] **Step 4: Run full regression suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all pre-existing tests plus Milestone A tests pass; environment-dependent existing skips remain skips, not converted to failures.

- [ ] **Step 5: Compile**

```bash
python -m compileall core tests main.py
```

Expected: success.

- [ ] **Step 6: Run forbidden-coupling greps**

```bash
python -c "from pathlib import Path; p=Path('core/tutorial/tour_engine.py').read_text(encoding='utf-8'); forbidden=['PySide6.QtWidgets','PySide6.QtGui','ProjectService','MediaImportService','FasterWhisper','workers.']; assert not any(x in p for x in forbidden)"
```

Expected: exit 0.

- [ ] **Step 7: Diff hygiene**

```bash
git diff --check
git status --short
```

Expected before commit: only intended Milestone A files; after commit: clean.

- [ ] **Step 8: Commit any final test-only gate changes**

```bash
git add tests
git commit -m "test: close guided tour milestone A gates"
```

If Step 1 required no new test because equivalent coverage already exists, do not create an empty commit.

---

# Milestone A Definition of Done

Milestone A is CLOSED only when all are true:

```text
[ ] TC132–TC138 PASS
[ ] TC145–TC147 PASS
[ ] TC152–TC157 PASS
[ ] TC166–TC173 PASS
[ ] TourEngine imports QtCore only
[ ] No concrete QWidget/QDialog implementation under core/tutorial
[ ] Scenario parser rejects executable/raw-signal/index fields
[ ] Asset confinement tests pass
[ ] Tour async callbacks are token-guarded
[ ] ACTION next-step preparation is queued
[ ] Cancel/cleanup is idempotent
[ ] Progress future schema is never overwritten
[ ] Corrupt progress cannot block startup
[ ] Atomic-write failure preserves previous canonical bytes
[ ] Full pre-existing regression suite passes
[ ] compileall passes
[ ] git diff --check passes
[ ] working tree clean
```

Milestone A deliberately stops before concrete `AnchorRegistry`, `NavigationAdapter`, `InteractionObserver`, `SpotlightLayer`, or `DialogLifecycleObserver`; those are Milestone B and consume the ports defined here.

---

# Execution Handoff

After this plan is reviewed and approved, execution should happen in an isolated worktree created at execution time via `superpowers:using-git-worktrees`.

Two supported execution modes:

1. **Subagent-Driven Development (recommended):** one fresh subagent per task, review each task before moving to the next.
2. **Executing Plans:** implement in batches with explicit checkpoints.

Do not begin Task A1 until this Milestone A plan has been approved.