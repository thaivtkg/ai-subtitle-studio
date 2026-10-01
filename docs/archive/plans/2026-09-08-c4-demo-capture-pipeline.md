# C4 Demo Capture Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic developer-side PNG/GIF UI capture pipeline that uses semantic Qt targets, isolated execution by default, validated atomic artifacts, a standalone CLI, and a sandboxed real-app fallback without changing Guided Tour runtime behavior.

**Architecture:** Implement the approved C4 design as seven milestones and seventeen TDD tasks. Pure contracts/orchestration live under `core/demo_capture`, Qt adapters under `ui/demo_capture`, and the developer entrypoint under `tools/demo_capture`; C4 consumes existing `AnchorRegistry` semantics but does not depend on `TourEngine`, Spotlight, progress, or `DemoMediaViewer`. Generation produces staged assets, validates them, and only then commits to `resources/tutorials/assets/`.

**Tech Stack:** Python 3.10, stdlib `unittest`, PySide6 6.11.1, Pillow 12.3.0 as developer/test-only image encoding/decoding dependency, GitHub Actions headless Qt (`QT_QPA_PLATFORM=offscreen` + Xvfb).

**Spec:** `docs/superpowers/specs/2026-09-08-c4-demo-capture-pipeline-design.md`

## Global Constraints

- Worktree: `D:\Temp\Translator`.
- Branch: `codex/help-center-guided-tour`.
- Baseline architecture: C3 closed at `8cff9bfcaf4ca469310b662f3a4d7905acba2668`; C4 design spec approved after commit `043031d4d7abf6019079d3aa89ead0dab89787ac`.
- Generation and consumption remain separate: no imports from `core.tutorial.tour_engine`, `ui.tutorial.spotlight_layer`, or `ui.tutorial.demo_media_viewer` inside C4.
- Reuse existing `ui/tutorial/anchor_registry.py` through an adapter; never create a coordinate registry.
- Default execution mode: `ISOLATED`.
- Default capture scope: `TARGET_REGION`.
- Default padding: `16 px`.
- Default logical viewport: `800 × 600`.
- Default FPS: `10`.
- Default output scale: `1.0`.
- Default wait timeout: `3000 ms`.
- Batch `--all`: `ISOLATED` only.
- PNG maximum: `2 MiB`.
- GIF maximum: `8 MiB`.
- Maximum dimensions: `1600 × 1200`; maximum `1,920,000` pixels/frame.
- GIF frame count: `2–200`; maximum duration: `20 s`.
- CI validates committed assets only; CI never regenerates them.
- Generation is source-checkout only; frozen/PyInstaller generation fails.
- Mode B never calls `main.main()` and never attaches to an existing user process.
- Mode B mutable state is redirected to a temporary profile and cleanup failure fails the run.
- Use TDD for every task: add RED test, run it, add minimum implementation, rerun focused tests, run milestone regression, commit.
- Use `python -m unittest`; do not introduce pytest solely for C4.
- Every task commit must pass `python -m compileall core ui tools tests` and `git diff --check` before push.
- No production tutorial scenario may use an invented semantic anchor. Contract/integration tests use fixture scenarios; production scenarios are added only when their anchor IDs already exist in the application registry.

---

# Milestone map

| Milestone | Spec TDD steps | Deliverable | Gate |
|---|---|---|---|
| **C4.1 Contract Foundation** | 1–2 | Immutable DTO/action contracts + validated registry | Pure-Python RED/GREEN suite |
| **C4.2 Semantic Automation** | 3–5 | Anchor adapter + explicit waits + semantic actions | No implicit wait / no coordinates |
| **C4.3 Capture Core** | 6–8 | Dynamic region capture + pad normalization + monotonic cadence | Deterministic Qt frame sequence |
| **C4.4 Artifact Pipeline** | 9–11 | PNG/GIF encoder + validator + atomic writer | Corrupt/oversized output cannot commit |
| **C4.5 Orchestration & CLI** | 12–14 | Runner + CLI + staged batch | Single and batch generation contracts |
| **C4.6 Isolated Production-Path Integration** | 15 | Real `MainWindow` Mode A → real PNG/GIF | Headless integration acceptance |
| **C4.7 Real-App Safety & CI Gate** | 16–17 | Mode B owned session + CI validation-only | No user-state pollution; full suite green |

---

# C4.1 — Contract Foundation

This milestone establishes all names and invariants that later tasks consume. Do not touch Qt or image libraries here.

## RED test inventory for C4.1

Continue numbering after C3 `TC186`.

| ID | RED test | Required failure before implementation |
|---|---|---|
| **TC187** | TARGET_REGION requires a non-empty semantic ID and defaults padding to 16 | `core.demo_capture.models` missing |
| **TC188** | FULL_WINDOW requires `semantic_id=None`; padding is accepted but ignored by capture semantics | model/validation missing |
| **TC189** | CaptureProfile defaults are 800×600 / 10 FPS / 1.0 / 3000 ms and rejects invalid bounds | profile missing |
| **TC190** | OutputSpec accepts basename + matching extension and rejects absolute/traversal/mismatch | output validation missing |
| **TC191** | Typed action DTOs are immutable and validate target/value/duration/timeout fields | action classes missing |
| **TC192** | CaptureScenario is immutable and retains ordered tuple actions | scenario missing |
| **TC193** | DemoScenarioRegistry rejects duplicate scenario IDs | registry missing |
| **TC194** | DemoScenarioRegistry rejects duplicate output filenames | registry missing |
| **TC195** | Registry construction performs structural validation only and never resolves a live QWidget/anchor | resolver must remain untouched |

### Task 1: Immutable DTOs and typed Action DSL

**Files:**
- Create: `core/demo_capture/__init__.py`
- Create: `core/demo_capture/models.py`
- Test: `tests/test_demo_capture_models_c4.py`

**Interfaces:**
- Produces: `CaptureScope`, `OutputFormat`, `ExecutionMode`, `CaptureTarget`, `CaptureProfile`, `OutputSpec`, `CaptureAction`, `ClickAction`, `SetTextAction`, `SelectAction`, `NavigateAction`, `WaitVisibleAction`, `WaitHiddenAction`, `WaitSettledAction`, `HoldAction`, `CaptureScenario`.
- Later tasks must import these names instead of redefining constants.

- [ ] **Step 1: Write TC187–TC192 as failing tests.**

```python
import unittest
from dataclasses import FrozenInstanceError

from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureScope,
    CaptureTarget,
    ClickAction,
    HoldAction,
    OutputFormat,
    OutputSpec,
    WaitVisibleAction,
)


class TestDemoCaptureModelsC4(unittest.TestCase):
    def test_tc187_target_region_requires_semantic_id_and_defaults_padding(self):
        target = CaptureTarget(semantic_id="workspace.generate_panel")
        self.assertEqual(target.scope, CaptureScope.TARGET_REGION)
        self.assertEqual(target.padding, 16)
        with self.assertRaises(ValueError):
            CaptureTarget(semantic_id=None)

    def test_tc188_full_window_requires_no_semantic_id(self):
        target = CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id=None, padding=16)
        self.assertEqual(target.scope, CaptureScope.FULL_WINDOW)
        with self.assertRaises(ValueError):
            CaptureTarget(scope=CaptureScope.FULL_WINDOW, semantic_id="workspace")

    def test_tc189_profile_defaults_and_bounds(self):
        profile = CaptureProfile()
        self.assertEqual(profile.window_size, (800, 600))
        self.assertEqual(profile.fps, 10)
        self.assertEqual(profile.output_scale, 1.0)
        self.assertEqual(profile.default_wait_timeout_ms, 3000)
        for kwargs in (
            {"window_size": (0, 600)}, {"fps": 0}, {"fps": 31},
            {"output_scale": 0}, {"default_wait_timeout_ms": 0},
        ):
            with self.assertRaises(ValueError):
                CaptureProfile(**kwargs)

    def test_tc190_output_spec_confines_filename(self):
        self.assertEqual(
            OutputSpec("demo.gif", OutputFormat.GIF).filename,
            "demo.gif",
        )
        for name in ("../demo.gif", "folder/demo.gif", "C:\\demo.gif", "/tmp/demo.gif"):
            with self.assertRaises(ValueError):
                OutputSpec(name, OutputFormat.GIF)
        with self.assertRaises(ValueError):
            OutputSpec("demo.png", OutputFormat.GIF)

    def test_tc191_actions_are_typed_immutable_and_validate(self):
        action = ClickAction("workspace.generate_button")
        with self.assertRaises(FrozenInstanceError):
            action.target = "other"
        with self.assertRaises(ValueError):
            ClickAction("")
        with self.assertRaises(ValueError):
            HoldAction(0)
        with self.assertRaises(ValueError):
            WaitVisibleAction("x", timeout_ms=0)

    def test_tc192_scenario_is_immutable_and_preserves_action_order(self):
        actions = (ClickAction("a"), HoldAction(100))
        scenario = CaptureScenario(
            id="sample",
            target=CaptureTarget("a"),
            profile=CaptureProfile(),
            actions=actions,
            output=OutputSpec("sample.gif", OutputFormat.GIF),
        )
        self.assertEqual(scenario.actions, actions)
        with self.assertRaises(FrozenInstanceError):
            scenario.id = "changed"
```

- [ ] **Step 2: Run the focused suite and confirm RED.**

Run:

```bash
python -m unittest tests.test_demo_capture_models_c4 -v
```

Expected: import failure for `core.demo_capture.models`.

- [ ] **Step 3: Add the minimum frozen models.**

Implementation shape:

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Optional, Tuple


class CaptureScope(str, Enum):
    TARGET_REGION = "TARGET_REGION"
    FULL_WINDOW = "FULL_WINDOW"


class OutputFormat(str, Enum):
    PNG = "PNG"
    GIF = "GIF"


class ExecutionMode(str, Enum):
    ISOLATED = "ISOLATED"
    REAL_APP = "REAL_APP"


@dataclass(frozen=True)
class CaptureTarget:
    semantic_id: Optional[str]
    scope: CaptureScope = CaptureScope.TARGET_REGION
    padding: int = 16

    def __post_init__(self) -> None:
        if self.padding < 0:
            raise ValueError("padding must be >= 0")
        if self.scope is CaptureScope.TARGET_REGION and not self.semantic_id:
            raise ValueError("TARGET_REGION requires semantic_id")
        if self.scope is CaptureScope.FULL_WINDOW and self.semantic_id is not None:
            raise ValueError("FULL_WINDOW requires semantic_id=None")


@dataclass(frozen=True)
class CaptureProfile:
    window_size: Tuple[int, int] = (800, 600)
    fps: int = 10
    output_scale: float = 1.0
    default_wait_timeout_ms: int = 3000

    def __post_init__(self) -> None:
        width, height = self.window_size
        if width <= 0 or height <= 0:
            raise ValueError("window dimensions must be > 0")
        if not 1 <= self.fps <= 30:
            raise ValueError("fps must be in range 1..30")
        if self.output_scale <= 0:
            raise ValueError("output_scale must be > 0")
        if self.default_wait_timeout_ms <= 0:
            raise ValueError("default_wait_timeout_ms must be > 0")
```

Implement the remaining frozen action/output/scenario classes with the validations asserted above; no Qt imports.

- [ ] **Step 4: Run TC187–TC192 GREEN.**

```bash
python -m unittest tests.test_demo_capture_models_c4 -v
python -m compileall core/demo_capture tests/test_demo_capture_models_c4.py
```

Expected: all six tests PASS.

- [ ] **Step 5: Commit.**

```bash
git add core/demo_capture tests/test_demo_capture_models_c4.py
git commit -m "feat(capture): add immutable capture contracts"
```

### Task 2: DemoScenarioRegistry structural validation

**Files:**
- Create: `core/demo_capture/registry.py`
- Test: `tests/test_demo_capture_registry_c4.py`

**Interfaces:**
- Consumes: `CaptureScenario` from Task 1.
- Produces: `DemoScenarioRegistry(scenarios)`, `.get(id)`, `.all()`, `.ids()`.
- Registry does not accept or call a target resolver.

- [ ] **Step 1: Write TC193–TC195 RED.**

```python
class TestDemoScenarioRegistryC4(unittest.TestCase):
    def _scenario(self, scenario_id, filename):
        return CaptureScenario(
            scenario_id,
            CaptureTarget("fixture.anchor"),
            CaptureProfile(),
            (HoldAction(50),),
            OutputSpec(filename, OutputFormat.GIF),
        )

    def test_tc193_duplicate_scenario_id_rejected(self):
        a = self._scenario("dup", "a.gif")
        b = self._scenario("dup", "b.gif")
        with self.assertRaises(ValueError):
            DemoScenarioRegistry((a, b))

    def test_tc194_duplicate_output_rejected(self):
        a = self._scenario("a", "same.gif")
        b = self._scenario("b", "same.gif")
        with self.assertRaises(ValueError):
            DemoScenarioRegistry((a, b))

    def test_tc195_registry_is_structural_only(self):
        registry = DemoScenarioRegistry((self._scenario("a", "a.gif"),))
        self.assertEqual(registry.ids(), ("a",))
        self.assertEqual(registry.get("a").output.filename, "a.gif")
        self.assertIsNone(registry.get("missing"))
```

- [ ] **Step 2: Confirm RED.**

```bash
python -m unittest tests.test_demo_capture_registry_c4 -v
```

Expected: import failure for `DemoScenarioRegistry`.

- [ ] **Step 3: Implement registry as immutable ordered storage.**

Use a tuple plus ID dictionary internally; validate duplicates during construction. Do not import `AnchorRegistry` or PySide6.

- [ ] **Step 4: Run C4.1 milestone gate.**

```bash
python -m unittest tests.test_demo_capture_models_c4 tests.test_demo_capture_registry_c4 -v
python -m compileall core/demo_capture tests/test_demo_capture_models_c4.py tests/test_demo_capture_registry_c4.py
git diff --check
```

Expected: TC187–TC195 PASS.

- [ ] **Step 5: Commit.**

```bash
git add core/demo_capture/registry.py tests/test_demo_capture_registry_c4.py
git commit -m "feat(capture): add scenario registry"
```

**C4.1 Acceptance Gate:** do not proceed unless TC187–TC195 are GREEN and `core/demo_capture` has no PySide6 import.

---

# C4.2 — Semantic Automation

### Task 3: AnchorRegistry capture adapter

**Files:**
- Create: `core/demo_capture/errors.py`
- Create: `ui/demo_capture/__init__.py`
- Create: `ui/demo_capture/anchor_registry_adapter.py`
- Test: `tests/test_demo_capture_target_resolver_c4.py`

**Interfaces:**
- Produces `CaptureErrorCode` and `CaptureRunError` with scenario/action context.
- Produces `AnchorRegistryCaptureAdapter.resolve_widget(semantic_id) -> QWidget`.
- `RESOLVED` must re-fetch through `get_widget(handle)`; no coordinates.

RED cases:
- **TC196:** RESOLVED returns the exact live QWidget.
- **TC197:** NOT_FOUND / NOT_VISIBLE / INVALID / resolver reason map to structured C4 target errors without coordinate fallback.

Minimum adapter flow:

```python
resolution = self._registry.resolve(semantic_id)
if resolution.status is AnchorStatus.RESOLVED:
    widget = self._registry.get_widget(resolution.handle)
    if widget is None:
        raise CaptureRunError(CaptureErrorCode.TARGET_INVALID, ...)
    return widget
raise CaptureRunError(mapped_code, ...)
```

Run:

```bash
python -m unittest tests.test_demo_capture_target_resolver_c4 -v
```

Commit: `feat(capture): adapt semantic anchor resolution`.

### Task 4: Explicit wait semantics

**Files:**
- Create: `core/demo_capture/ports.py`
- Create: `ui/demo_capture/action_driver.py`
- Test: `tests/test_demo_capture_actions_c4.py`

**Interfaces:**
- `UIActionDriver.execute(action, *, profile, tick)` is cooperative; `tick()` is internal orchestration, never stored in a scenario.
- Constructor receives resolver, navigation adapter, event-pump callable, and monotonic clock callable for deterministic tests.

RED cases:
- **TC198:** WAIT_VISIBLE: RESOLVED succeeds; NOT_FOUND/NOT_VISIBLE poll; INVALID/resolver error fail; timeout returns `WAIT_TIMEOUT`.
- **TC199:** WAIT_HIDDEN: NOT_FOUND/NOT_VISIBLE succeed; RESOLVED polls; INVALID fails.
- Wait timeout defaults to `CaptureProfile.default_wait_timeout_ms` when action timeout is `None`.

Wait loop shape:

```python
while True:
    self._event_pump()
    status = self._resolver.status(action.target)
    if success(status):
        return
    if fatal(status):
        raise ...
    tick()
    if elapsed_ms >= timeout_ms:
        raise CaptureRunError(CaptureErrorCode.WAIT_TIMEOUT, ...)
```

Do not use `time.sleep()`.

Commit: `feat(capture): add explicit semantic waits`.

### Task 5: CLICK / SET_TEXT / SELECT / NAVIGATE / WAIT_SETTLED / HOLD

**Files:**
- Modify: `ui/demo_capture/action_driver.py`
- Create: `ui/demo_capture/navigation_adapter.py`
- Test: `tests/test_demo_capture_actions_c4.py`

**Interfaces:**
- CLICK resolves immediately and calls the Qt widget interaction; it never waits implicitly.
- SET_TEXT replaces text.
- SELECT selects by stable text/data value, not numeric index as primary contract.
- NAVIGATE delegates once to a capture navigation adapter and does not wait.
- WAIT_SETTLED compares a structural signature across consecutive event-pump cycles.
- HOLD pumps events and calls `tick()` until its monotonic duration expires.

RED cases:
- **TC200:** CLICK on NOT_VISIBLE fails immediately and does not poll.
- **TC201:** NAVIGATE calls navigation exactly once and does not call WAIT_VISIBLE.
- **TC202:** HOLD(800) pumps events/ticks cooperatively and never calls `time.sleep`.
- **TC203:** SET_TEXT replaces existing QLineEdit/QTextEdit text.
- **TC204:** SELECT resolves a combo option by stable value/text; missing option fails `ACTION_FAILED`.
- **TC205:** WAIT_SETTLED requires consecutive identical geometry/visibility structural signatures and times out deterministically when the structure keeps changing.

Run milestone gate:

```bash
python -m unittest \
  tests.test_demo_capture_target_resolver_c4 \
  tests.test_demo_capture_actions_c4 -v
python -m compileall core/demo_capture ui/demo_capture tests
```

Commit: `feat(capture): add semantic action driver`.

**C4.2 Acceptance Gate:** TC196–TC205 GREEN; grep C4 files for `pyautogui`, raw screen coordinates, or implicit sleeps and require zero matches.

---

# C4.3 — Capture Core

### Task 6: TARGET_REGION and FULL_WINDOW frame capture

**Files:**
- Create: `ui/demo_capture/frame_capture.py`
- Test: `tests/test_demo_capture_frame_capture_c4.py`

**Interfaces:**
- `FrameCaptureService.capture(target: CaptureTarget, main_window: QWidget) -> QImage`.
- TARGET_REGION resolves the widget on every call, maps geometry to its window, expands padding, clips to root bounds, grabs the root, then crops.
- FULL_WINDOW grabs the supplied capture-owned main window.

RED cases:
- **TC206:** region geometry includes exactly 16 px padding where room exists.
- **TC207:** padding clips at window edges and never produces out-of-bounds crop.
- **TC208:** FULL_WINDOW returns the main-window image dimensions.
- **TC209:** moving/resizing the target between calls changes the next crop; cached QRect is forbidden.

Implementation shape:

```python
widget = resolver.resolve_widget(target.semantic_id)
root = widget.window()
origin = widget.mapTo(root, QPoint(0, 0))
rect = QRect(origin, widget.size()).adjusted(-p, -p, p, p).intersected(root.rect())
return root.grab().copy(rect).toImage()
```

Commit: `feat(capture): capture semantic target regions`.

### Task 7: FrameNormalizer — pad, never stretch

**Files:**
- Create: `ui/demo_capture/frame_normalizer.py`
- Test: `tests/test_demo_capture_frame_normalizer_c4.py`

**Interfaces:**
- `FrameNormalizer.normalize(frames: Sequence[QImage], output_scale: float) -> tuple[QImage, ...]`.
- Canonical canvas is max width × max height across the sequence.
- Smaller frames are centered on a transparent ARGB canvas; source pixels are copied 1:1 before optional final whole-canvas scaling.

RED cases:
- **TC210:** 100×50 and 200×100 frames become two 200×100 frames without stretching the 100×50 source pixels.
- **TC211:** centering offset is deterministic using integer floor division.
- **TC212:** output_scale=2.0 scales the canonical canvas after padding, not each raw frame independently.
- **TC213:** empty frame sequence fails `CAPTURE_FAILED`.

Commit: `feat(capture): normalize frames with centered padding`.

### Task 8: Monotonic frame cadence

**Files:**
- Create: `core/demo_capture/frame_clock.py`
- Test: `tests/test_demo_capture_frame_clock_c4.py`

**Interfaces:**
- `FrameClock(fps, monotonic)`.
- `start()` records monotonic origin.
- `due_count()` reports how many fixed-rate frame slots became due since the previous call and advances by interval `1/fps`.

RED cases:
- **TC214:** 10 FPS produces one due frame at each 100 ms boundary.
- **TC215:** a delayed 350 ms tick reports three due slots rather than changing GIF frame duration.
- **TC216:** monotonic time moving backwards raises `CAPTURE_FAILED` rather than creating negative timing.

Run milestone gate:

```bash
python -m unittest \
  tests.test_demo_capture_frame_capture_c4 \
  tests.test_demo_capture_frame_normalizer_c4 \
  tests.test_demo_capture_frame_clock_c4 -v
```

Commit: `feat(capture): add monotonic frame cadence`.

**C4.3 Acceptance Gate:** TC206–TC216 GREEN, no frame stretch before canonical padding, no cached target rectangle.

---

# C4.4 — Artifact Pipeline

### Task 9: PNG/GIF encoder implementation

**Files:**
- Create: `requirements-dev.txt`
- Create: `ui/demo_capture/encoder.py`
- Test: `tests/test_demo_capture_encoder_c4.py`

**Implementation choice for this plan:** use `Pillow==12.3.0` as a **developer/test-only** dependency. Do not add Pillow to `requirements-runtime.txt`.

**Interfaces:**
- `PillowAssetEncoder.encode_png(frame: QImage, path: Path) -> None`.
- `PillowAssetEncoder.encode_gif(frames: Sequence[QImage], path: Path, fps: int) -> None`.
- QImage is converted to RGBA without changing dimensions.
- GIF delay is `round(1000 / fps)` ms, loop forever, and contains every normalized frame.

RED cases:
- **TC217:** PNG output has PNG magic and decodes to exact dimensions/pixels.
- **TC218:** GIF with two frames has GIF magic, `n_frames == 2`, and expected frame delay.
- **TC219:** GIF with fewer than two frames fails `ENCODE_FAILED`.

Developer dependency file:

```text
Pillow==12.3.0
```

Commit: `feat(capture): encode tutorial png and gif assets`.

### Task 10: TutorialAssetValidator

**Files:**
- Create: `core/demo_capture/validation.py`
- Test: `tests/test_demo_capture_asset_validation_c4.py`

**Interfaces:**
- `AssetValidationPolicy` contains the locked limits.
- `TutorialAssetValidator.validate_file(path, output_spec) -> None`.
- `validate_registry_assets(registry, asset_root) -> None` validates committed mappings without QApplication/MainWindow.

RED cases:
- **TC220:** valid PNG under limits passes real decode.
- **TC221:** valid GIF with 2–200 frames and ≤20 s passes.
- **TC222:** wrong extension/magic pairing fails.
- **TC223:** truncated/corrupt image fails even if filename/size look valid.
- **TC224:** width, height, pixel count, filesize, GIF frame count, and GIF duration each fail at one-over-limit.
- **TC225:** differing GIF frame dimensions fail canonical-frame invariant.
- **TC226:** registry mapping to a missing committed asset fails validation.

Use Pillow for decode inspection in this developer subsystem; do not import Qt UI classes.

Commit: `feat(capture): validate generated tutorial assets`.

### Task 11: ArtifactWriter atomic replace

**Files:**
- Create: `core/demo_capture/artifact_writer.py`
- Test: `tests/test_demo_capture_artifact_writer_c4.py`

**Interfaces:**
- `ArtifactWriter(asset_root)` owns the final root.
- `commit(staged_path, output_spec)` uses `os.replace` only after validation has succeeded upstream.
- Final path is derived only from `OutputSpec.filename`.

RED cases:
- **TC227:** validated staged file atomically replaces old final content.
- **TC228:** pre-commit failure leaves old asset byte-for-byte unchanged.
- **TC229:** staged path/final filename traversal outside asset root is rejected.
- **TC230:** temporary/staging file is cleaned after successful replace or aborted run.

Run milestone gate:

```bash
python -m unittest \
  tests.test_demo_capture_encoder_c4 \
  tests.test_demo_capture_asset_validation_c4 \
  tests.test_demo_capture_artifact_writer_c4 -v
```

Commit: `feat(capture): atomically publish validated assets`.

**C4.4 Acceptance Gate:** TC217–TC230 GREEN; `requirements-runtime.txt` unchanged; corrupt/oversized files cannot reach final asset path.

---

# C4.5 — Orchestration & CLI

### Task 12: DemoCaptureRunner single-scenario orchestration

**Files:**
- Create: `core/demo_capture/runner.py`
- Test: `tests/test_demo_capture_runner_c4.py`

**Interfaces:**
- Runner receives environment factory, action driver, frame clock, capturer, normalizer, encoder, validator.
- `capture_to_staging(scenario, mode, staging_dir) -> Path` never commits final assets.
- A higher-level `generate_one(...)` validates staged output, exits/cleans environment successfully, then calls `ArtifactWriter.commit`.

RED cases:
- **TC231:** initial frame is captured before actions and final frame after actions.
- **TC232:** actions execute in declared order; waits/holds invoke runner tick and preserve frame cadence.
- **TC233:** first failing action stops later actions and returns structured scenario/action/error context.
- **TC234:** encode/validation failure does not call ArtifactWriter.
- **TC235:** environment cleanup executes in `finally`; cleanup failure turns apparent capture success into overall failure and prevents commit.

Core loop shape:

```python
with environment_factory.open(mode, scenario.profile) as env:
    clock.start()
    frames = [capturer.capture(scenario.target, env.main_window)]
    for index, action in enumerate(scenario.actions):
        driver.execute(action, profile=scenario.profile, tick=tick)
    frames.append(capturer.capture(scenario.target, env.main_window))
    normalized = normalizer.normalize(frames, scenario.profile.output_scale)
    encoder.encode(...)
    validator.validate_file(...)
# commit only after context-manager cleanup succeeded
```

Commit: `feat(capture): orchestrate single scenario capture`.

### Task 13: Standalone CLI

**Files:**
- Create: `tools/__init__.py` only if absent.
- Create: `tools/demo_capture/__init__.py`
- Create: `tools/demo_capture/__main__.py`
- Create: `tools/demo_capture/cli.py`
- Test: `tests/test_demo_capture_cli_c4.py`

**Interfaces:**
- `main(argv: Optional[Sequence[str]] = None) -> int`.
- Subcommands: `list`, `generate`, `validate`.
- `generate <id>` XOR `generate --all`.
- `--mode isolated` default; `--mode real` explicit.
- `list` and `validate` use lazy imports and must not instantiate QApplication/MainWindow.
- Source-checkout guard rejects `sys.frozen` generation with exit code 4.

RED cases:
- **TC236:** `list` returns 0 and prints registry metadata without QApplication construction.
- **TC237:** `generate scenario-id` chooses ISOLATED by default.
- **TC238:** `generate foo --all` is parser error/exit 2.
- **TC239:** unknown scenario is exit 2; runtime generation failure is exit 1; validation failure is exit 3; unavailable environment is exit 4.
- **TC240:** frozen generation returns exit 4 and does not touch packaged resources.
- **TC241:** importing/running CLI never imports or calls `main.main()`.

`__main__.py` must contain only:

```python
from .cli import main

raise SystemExit(main())
```

Commit: `feat(capture): add standalone demo capture cli`.

### Task 14: `--all` staged batch

**Files:**
- Create: `core/demo_capture/batch.py`
- Modify: `tools/demo_capture/cli.py`
- Test: `tests/test_demo_capture_batch_c4.py`

**Interfaces:**
- `DemoCaptureBatchRunner.run_all(registry, mode, staging_root)`.
- Mode must be ISOLATED.
- Fresh environment per scenario is enforced by calling single-scenario runner separately.
- All scenarios execute to staging; errors are collected; no final commit unless every scenario passes.
- Commit phase uses per-file atomic replace; no claim of multi-file transaction safety after commit begins.

RED cases:
- **TC242:** two passing scenarios use two distinct environments and both commit after all validation passes.
- **TC243:** one failing scenario prevents every final asset change even when earlier/later scenarios pass.
- **TC244:** independent scenarios continue after one failure so result contains complete failure report.
- **TC245:** `--all --mode real` fails before creating an environment.
- **TC246:** final commit occurs only after the last staged scenario validates.

Run milestone gate:

```bash
python -m unittest \
  tests.test_demo_capture_runner_c4 \
  tests.test_demo_capture_cli_c4 \
  tests.test_demo_capture_batch_c4 -v
python -m compileall core ui tools tests
git diff --check
```

Commit: `feat(capture): add staged batch generation`.

**C4.5 Acceptance Gate:** TC231–TC246 GREEN; `main.py` unchanged by CLI work; `--all` cannot enter REAL_APP.

---

# C4.6 — Isolated Production-Path Integration

### Task 15: IsolatedAppFactory → real PNG/GIF

**Files:**
- Create: `ui/demo_capture/isolated_app_factory.py`
- Create: `tests/test_demo_capture_integration_c4.py`
- Reuse without modification unless a regression is proven: `ui/Gui.py`, `ui/tutorial/anchor_registry.py`.

**Interfaces:**
- Factory creates/reuses `QApplication`, creates a temporary `LOCALAPPDATA` sandbox, calls `RuntimePaths.ensure_user_data_dirs()`, builds `MainWindow` with mocked project/media services, resizes logical viewport, calls `show()` + `processEvents()`, and owns cleanup.
- Integration fixture may register a **test-only** semantic anchor into `window.tour_anchor_registry`; it must not add invented production anchors to `ui/Gui.py`.

RED cases:
- **TC247:** isolated 800×600 capture creates a real decodable PNG from a visible test anchor using TARGET_REGION + padding.
- **TC248:** isolated scenario with a Qt geometry transition/HOLD creates a real animated GIF with at least two frames and canonical dimensions.
- **TC249:** test records no DesktopInteractionPort/OS mouse-keyboard call in ISOLATED mode.
- **TC250:** two isolated sessions use different temporary profiles and leave user `%LOCALAPPDATA%` untouched.

Test pattern must follow the existing MainWindow lifecycle already proven in `tests/test_main_window_c2.py`: QApplication singleton, temporary state, `MainWindow(...)`, `show()`, `processEvents()`, close/deleteLater/processEvents cleanup.

Run:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest tests.test_demo_capture_integration_c4 -v
```

On Windows PowerShell use:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m unittest tests.test_demo_capture_integration_c4 -v
```

Commit: `feat(capture): integrate isolated main window capture`.

**C4.6 Acceptance Gate:** TC247–TC250 GREEN on a PySide6-capable environment and on CI/Xvfb before opening Mode B.

---

# C4.7 — Real-App Safety & CI Gate

### Task 16: Capture-owned REAL_APP session

**Files:**
- Create: `ui/demo_capture/real_app_capture_factory.py`
- Create: `ui/demo_capture/real_app_session.py`
- Test: `tests/test_demo_capture_real_app_c4.py`

**Interfaces:**
- Factory constructs `MainWindow` directly from production service classes without importing/calling `main.main()`.
- Session saves/restores overridden environment, creates temporary profile, tracks its own MainWindow and child/parented top-level dialogs, and closes only owned objects.
- No attach-existing capability or API exists.
- Real desktop interaction, if later needed by a scenario, remains behind a `DesktopInteractionPort`; Qt semantic actions remain first choice.

RED cases:
- **TC251:** REAL_APP uses temporary LocalAppData paths for settings/progress/recovery and never the pre-test user path.
- **TC252:** constructing REAL_APP does not acquire `SingleInstanceGuard`, scan user recovery, or import/call `main.main()`.
- **TC253:** cleanup closes owned MainWindow + parented dialog but leaves an unrelated pre-existing top-level QWidget open.
- **TC254:** environment variables are restored after success and after scenario failure.
- **TC255:** injected cleanup failure reports `CLEANUP_FAILED` and final ArtifactWriter is never called.
- **TC256:** public C4 API exposes no attach-existing mode.

Commit: `feat(capture): add sandboxed real app capture session`.

### Task 17: CI validation-only gate and final regression

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `requirements-dev.txt`
- Test: all C4 tests plus existing repository suite.

**Interfaces:**
- CI installs runtime requirements plus `requirements-dev.txt`.
- Existing unit/headless UI discovery remains.
- Add a distinct validation command:

```bash
python -m tools.demo_capture validate
```

- Compile check becomes:

```bash
python -m compileall core ui workers tools tests
```

- CI must not invoke `generate`.

RED/verification cases:
- **TC257:** CI workflow text contains `python -m tools.demo_capture validate`.
- **TC258:** CI workflow contains no `tools.demo_capture generate` command.
- **TC259:** validation command is QApplication-free and succeeds when registry/output mapping is valid.
- **TC260:** validation command fails exit 3 for a fixture registry pointing at corrupt/missing asset.

Suggested small workflow-contract test in `tests/test_demo_capture_ci_contract_c4.py`:

```python
from pathlib import Path
import unittest


class TestDemoCaptureCIContractC4(unittest.TestCase):
    def test_tc257_tc258_ci_validates_but_never_generates(self):
        text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m tools.demo_capture validate", text)
        self.assertNotIn("tools.demo_capture generate", text)
```

Run final gates:

```bash
python -m unittest discover -s tests -p "test*.py" -v
python -m compileall core ui workers tools tests
git diff --check
python -m tools.demo_capture validate
```

Then inspect scope:

```bash
git diff --stat 8cff9bf..HEAD
git diff 8cff9bf..HEAD -- core/tutorial ui/tutorial/demo_media_viewer.py ui/tutorial/spotlight_layer.py main.py
```

Expected:
- no behavioral C3 modification;
- `main.py` has no C4 CLI/capture lifecycle;
- if any existing C3 file changed due a proven regression, stop for architecture review before accepting C4.

Commit: `ci: validate demo capture assets without regeneration`.

**C4.7 / Final Acceptance Gate:** TC187–TC260 GREEN, full existing test suite GREEN, compileall GREEN, diff-check GREEN, CI GREEN, worktree clean after final commit/push.

---

# Test numbering summary

```text
C4.1  TC187–TC195  Models + registry
C4.2  TC196–TC205  Semantic resolver + waits/actions
C4.3  TC206–TC216  Capture geometry + normalization + frame clock
C4.4  TC217–TC230  Encoder + validation + atomic writer
C4.5  TC231–TC246  Runner + CLI + batch
C4.6  TC247–TC250  Isolated MainWindow integration
C4.7  TC251–TC260  Real-app safety + CI contract
```

Total planned C4 acceptance cases: **74** numbered checks (`TC187` through `TC260` inclusive). A single numbered case may contain multiple assertions for one contract; do not inflate test count by splitting every assertion into a separate ID.

---

# Commit sequence

Use one reviewable commit per task:

```text
1  feat(capture): add immutable capture contracts
2  feat(capture): add scenario registry
3  feat(capture): adapt semantic anchor resolution
4  feat(capture): add explicit semantic waits
5  feat(capture): add semantic action driver
6  feat(capture): capture semantic target regions
7  feat(capture): normalize frames with centered padding
8  feat(capture): add monotonic frame cadence
9  feat(capture): encode tutorial png and gif assets
10 feat(capture): validate generated tutorial assets
11 feat(capture): atomically publish validated assets
12 feat(capture): orchestrate single scenario capture
13 feat(capture): add standalone demo capture cli
14 feat(capture): add staged batch generation
15 feat(capture): integrate isolated main window capture
16 feat(capture): add sandboxed real app capture session
17 ci: validate demo capture assets without regeneration
```

Do not squash during development; preserve task commits until C4 review is complete.

---

# Reviewer checkpoints

Pause for review after these gates rather than running all 17 tasks blindly:

1. **After C4.1:** approve DTO names/invariants and registry before Qt code.
2. **After C4.2:** verify no implicit waits, coordinates, or OS input entered the design.
3. **After C4.3:** visually/structurally verify pad-not-stretch and dynamic geometry.
4. **After C4.4:** inspect real PNG/GIF and validator rejection cases before orchestration.
5. **After C4.5:** review CLI exit semantics and batch all-or-nothing pre-commit behavior.
6. **After C4.6:** require CI/headless real-MainWindow GIF proof before Mode B.
7. **After C4.7:** full acceptance + scope diff + clean worktree.

---

# First execution slice

The first implementation session should execute **C4.1 only (Tasks 1–2)**. Do not begin Qt adapters in the same slice.

Required evidence to report at the C4.1 review gate:

```text
BRANCH: codex/help-center-guided-tour
TASKS: C4.1 Task 1–2
RED:
  TC187–TC192 failed before models existed
  TC193–TC195 failed before registry existed
GREEN:
  TC187–TC195 PASS
CHECKS:
  compileall PASS
  git diff --check PASS
  no PySide6 import under core/demo_capture PASS
COMMITS:
  <task-1-sha>
  <task-2-sha>
WORKTREE: CLEAN
PUSHED: YES
```

Only after that review passes should C4.2 open.
