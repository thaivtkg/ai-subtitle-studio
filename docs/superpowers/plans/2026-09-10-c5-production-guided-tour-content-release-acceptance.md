# C5 Production Guided Tour Content & Release Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the locked nine-step `getting_started` v2 production Guided Tour with exactly six production semantic anchors, one validated local C4-generated GIF, zero business-state mutation, and passing automated/manual/PyInstaller release gates.

**Architecture:** C5 is content/config/composition work on top of the already-closed C1–C4 runtime. `ui/Gui.py` exposes six existing QWidgets through the existing `AnchorRegistry.register()` API, `resources/tutorials/getting_started.json` supplies the normative nine-step immutable content, and C4 supplies one developer-generated local GIF without changing C4 runner/encoder/validator behavior. The plan deliberately adds no TourEngine behavior, no route, no resolver abstraction, and no business workflow automation.

**Tech Stack:** Python 3.11 release environment, Python `unittest`, PySide6/QtTest, existing `core.tutorial` runtime, existing C4 demo-capture pipeline, Pillow asset validation, PyInstaller on Windows.

**Spec:** `docs/superpowers/specs/2026-09-10-c5-production-guided-tour-content-release-acceptance-design.md`

## Global Constraints

- Base contract: `master@e0fbea153e889a6127e6d4403ae8fe343645b7d1`.
- Implementation branch: `codex/c5-production-guided-tour`.
- `guide_id` remains exactly `getting_started`; production `content_version` becomes exactly `2`.
- Production tour has exactly 9 steps in this order: `welcome`, `dashboard_overview`, `create_project_entry`, `open_video_workspace`, `subtitle_editor_overview`, `ai_workspace_overview`, `generation_demo`, `export_center_overview`, `finish`.
- Exactly six production semantic anchors are allowed: `dashboard.root`, `dashboard.new_project`, `navigation.video_workspace`, `workspace.subtitle_editor`, `workspace.ai_generation`, `export_center.root`.
- Production composition uses `AnchorRegistry.register(...)` only; do not add production `register_resolver(...)` bindings.
- `open_video_workspace` is the only `ACTION`; it uses `REQUIRED + CLICK`.
- The other five targeted steps use `FALLBACK_TO_INFO`.
- Do not add a `subtitle_editor` route or any new route/subroute.
- Do not modify `core/tutorial/tour_engine.py`, `core/tutorial/models.py`, `core/tutorial/catalog.py`, `core/tutorial/ports.py`, `core/tutorial/environment.py`, `core/tutorial/progress_store.py`, `ui/tutorial/anchor_registry.py`, `ui/tutorial/navigation_adapter.py`, `ui/tutorial/interaction_observer.py`, `ui/tutorial/spotlight_layer.py`, `ui/tutorial/demo_media_viewer.py`, `core/demo_capture/*`, or `ui/demo_capture/*` unless a separately approved direct regression is proven.
- Production Tour runtime must not create/open/save Projects, import/download media, start Whisper/model generation, require CUDA, or execute exports.
- Guide-level and step-level preconditions remain empty; do not add TourEngine step-precondition behavior.
- DEMO asset path is exactly `assets/getting_started_generation.gif`; `media_type` is exactly `gif`; source GIF is 16:9.
- C4 CI validates committed assets only; CI must not regenerate the GIF.
- At execution time, create/use an isolated worktree via `superpowers:using-git-worktrees` before editing code.
- Use TDD: RED test first, minimal GREEN implementation second, focused test rerun, then commit.

---

## File Map

### Production files modified

- `ui/Gui.py`
  - Promote the existing New Project button local variable to `self.btn_new_project`.
  - Add `_register_tour_anchors()`.
  - Call it immediately after `self.tour_anchor_registry = AnchorRegistry()` and before observer/router/engine wiring.

- `resources/tutorials/getting_started.json`
  - Replace the one-step placeholder with the locked nine-step schema-v1 guide.
  - Set `content_version` to `2`.

- `tools/demo_capture/cli.py`
  - Replace the empty `_get_registry()` content with exactly one production C5 `CaptureScenario`.
  - Do not change CLI behavior, runner behavior, frozen guard, validation behavior, or output root.

- `resources/tutorials/assets/getting_started_generation.gif`
  - Create only by the existing C4 capture pipeline.
  - Commit only after `python -m tools.demo_capture validate` passes.

### Tests created

- `tests/test_c5_production_tour_contract.py`
  - Production JSON identity/order/schema/DEMO contract.

- `tests/test_c5_production_anchor_bootstrap.py`
  - Exact six `AnchorRegistry.register()` bindings and runtime resolution to the intended QWidgets.

- `tests/test_c5_production_tour_integration.py`
  - Real ACTION click path, post-ACTION back fence, full safe-tour zero-mutation/completion integration.

- `tests/test_c5_demo_capture_content.py`
  - Production C4 registry/scenario/CLI list contract.

### Files explicitly not changed

```text
core/tutorial/*
ui/tutorial/*
core/demo_capture/*
ui/demo_capture/*
build/ai_subtitle_studio.spec
resources/tutorials/catalog.json
```

`build/ai_subtitle_studio.spec` already packages the whole `resources/` directory; packaged smoke is the proof that this remains sufficient.

---

### Task 1: Lock the production Getting Started v2 content with parser-backed tests

**Files:**
- Create: `tests/test_c5_production_tour_contract.py`
- Modify: `resources/tutorials/getting_started.json`

**Interfaces:**
- Consumes: `TourCatalog(Path)`, `TourParser`, `TourStepType`, `TargetPolicy`, `InteractionKind`, `SurfaceSpec` from the closed C1 runtime.
- Produces: the real production guide `getting_started`, `content_version == 2`, with exactly nine parser-valid steps for all later integration tests.

- [ ] **Step 1: Write the failing production contract tests**

Create `tests/test_c5_production_tour_contract.py`:

```python
import json
import unittest
from pathlib import Path

from core.tutorial.catalog import TourCatalog
from core.tutorial.models import InteractionKind, TargetPolicy, TourStepType


class TestC5ProductionTourContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1] / "resources" / "tutorials"
        cls.guide_path = cls.root / "getting_started.json"

    def _load(self):
        raw = json.loads(self.guide_path.read_text(encoding="utf-8"))
        catalog = TourCatalog(self.root)
        guides = catalog.load_all()
        self.assertEqual(catalog.errors, ())
        self.assertEqual([guide.guide_id for guide in guides], ["getting_started"])
        guide = catalog.get_guide("getting_started")
        self.assertIsNotNone(guide)
        return raw, guide

    def test_tc257_identity_order_and_step_types(self):
        raw, guide = self._load()
        expected_ids = [
            "welcome",
            "dashboard_overview",
            "create_project_entry",
            "open_video_workspace",
            "subtitle_editor_overview",
            "ai_workspace_overview",
            "generation_demo",
            "export_center_overview",
            "finish",
        ]
        expected_types = [
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.ACTION,
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.DEMO,
            TourStepType.INFO,
            TourStepType.INFO,
        ]

        self.assertEqual(raw["guide_id"], "getting_started")
        self.assertEqual(raw["content_version"], 2)
        self.assertEqual(guide.content_version, 2)
        self.assertEqual([step.step_id for step in guide.steps], expected_ids)
        self.assertEqual([step.step_type for step in guide.steps], expected_types)
        self.assertEqual(len(guide.steps), 9)
        self.assertEqual(guide.preconditions, ())
        self.assertTrue(all(step.preconditions == () for step in guide.steps))

    def test_tc258_surfaces_anchors_policies_and_action_contract(self):
        _, guide = self._load()
        by_id = {step.step_id: step for step in guide.steps}

        self.assertEqual(by_id["welcome"].surface.route, "dashboard")
        self.assertEqual(by_id["dashboard_overview"].surface.route, "dashboard")
        self.assertEqual(by_id["create_project_entry"].surface.route, "dashboard")
        self.assertEqual(by_id["open_video_workspace"].surface.route, "dashboard")
        self.assertEqual(by_id["subtitle_editor_overview"].surface.route, "workspace")
        self.assertIsNone(by_id["subtitle_editor_overview"].surface.subroute)
        self.assertEqual(by_id["ai_workspace_overview"].surface.route, "workspace")
        self.assertEqual(by_id["ai_workspace_overview"].surface.subroute, "generate")
        self.assertEqual(by_id["generation_demo"].surface.route, "workspace")
        self.assertEqual(by_id["generation_demo"].surface.subroute, "generate")
        self.assertEqual(by_id["export_center_overview"].surface.route, "export_center")
        self.assertIsNone(by_id["finish"].surface)

        expected_anchors = {
            "dashboard_overview": "dashboard.root",
            "create_project_entry": "dashboard.new_project",
            "open_video_workspace": "navigation.video_workspace",
            "subtitle_editor_overview": "workspace.subtitle_editor",
            "ai_workspace_overview": "workspace.ai_generation",
            "export_center_overview": "export_center.root",
        }
        self.assertEqual(
            {step_id: by_id[step_id].anchor for step_id in expected_anchors},
            expected_anchors,
        )

        action = by_id["open_video_workspace"]
        self.assertEqual(action.target_policy, TargetPolicy.REQUIRED)
        self.assertEqual(action.interaction.kind, InteractionKind.CLICK)
        self.assertFalse(action.safety.allow_back)
        self.assertFalse(by_id["subtitle_editor_overview"].safety.allow_back)

        for step_id in (
            "dashboard_overview",
            "create_project_entry",
            "subtitle_editor_overview",
            "ai_workspace_overview",
            "export_center_overview",
        ):
            self.assertEqual(by_id[step_id].target_policy, TargetPolicy.FALLBACK_TO_INFO)

        self.assertEqual(
            [step.step_id for step in guide.steps if step.step_type is TourStepType.ACTION],
            ["open_video_workspace"],
        )

    def test_tc259_demo_source_and_runtime_contract(self):
        raw, guide = self._load()
        raw_demo = next(
            step["demo"] for step in raw["steps"] if step["step_id"] == "generation_demo"
        )
        runtime_demo = next(
            step.demo for step in guide.steps if step.step_id == "generation_demo"
        )

        self.assertEqual(raw_demo["asset"], "assets/getting_started_generation.gif")
        self.assertEqual(raw_demo["media_type"], "gif")
        self.assertEqual(raw_demo["fit"], "contain")
        self.assertEqual(runtime_demo.media_type, "gif")
        self.assertEqual(runtime_demo.fit, "contain")
        self.assertEqual(Path(runtime_demo.asset).name, "getting_started_generation.gif")
        self.assertEqual(Path(runtime_demo.asset).parent, (self.root / "assets").resolve())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify RED against the current one-step placeholder**

Run:

```bash
python -m unittest tests.test_c5_production_tour_contract -v
```

Expected: FAIL because `content_version` is still `1`, only `welcome` exists, and the six anchors/ACTION/DEMO contracts are absent.

- [ ] **Step 3: Replace the production JSON with the locked schema-v1 document**

Replace `resources/tutorials/getting_started.json` with:

```json
{
  "schema_version": 1,
  "guide_id": "getting_started",
  "content_version": 2,
  "title": "Làm quen với AI Subtitle Studio",
  "description": "Tham quan an toàn các khu vực chính và quy trình làm việc của AI Subtitle Studio.",
  "category": "getting_started",
  "estimated_minutes": 3,
  "preconditions": [],
  "steps": [
    {
      "step_id": "welcome",
      "type": "INFO",
      "surface": { "route": "dashboard" },
      "callout": {
        "title": "Chào mừng",
        "body": "Tour này giới thiệu các khu vực chính của AI Subtitle Studio mà không tạo Project, nhập media hay chạy AI thật.",
        "placement": "center"
      },
      "safety": {
        "allow_back": false,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "dashboard_overview",
      "type": "INFO",
      "surface": { "route": "dashboard" },
      "anchor": "dashboard.root",
      "target_policy": "FALLBACK_TO_INFO",
      "callout": {
        "title": "Dashboard",
        "body": "Dashboard là điểm bắt đầu để theo dõi và truy cập các khu vực làm việc chính.",
        "placement": "auto"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "create_project_entry",
      "type": "INFO",
      "surface": { "route": "dashboard" },
      "anchor": "dashboard.new_project",
      "target_policy": "FALLBACK_TO_INFO",
      "callout": {
        "title": "Tạo Dự Án Mới",
        "body": "Đây là điểm bắt đầu một Project thật. Trong tour này bạn không cần bấm nút và không có Project nào được tạo.",
        "placement": "auto"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "open_video_workspace",
      "type": "ACTION",
      "surface": { "route": "dashboard" },
      "anchor": "navigation.video_workspace",
      "target_policy": "REQUIRED",
      "callout": {
        "title": "Mở Video Workspace",
        "body": "Hãy bấm Video Workspace để tiếp tục. Tour chỉ quan sát thao tác này và không tự bấm thay bạn.",
        "placement": "auto"
      },
      "interaction": { "kind": "CLICK" },
      "safety": {
        "allow_back": false,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "subtitle_editor_overview",
      "type": "INFO",
      "surface": { "route": "workspace" },
      "anchor": "workspace.subtitle_editor",
      "target_policy": "FALLBACK_TO_INFO",
      "callout": {
        "title": "Subtitle Editor",
        "body": "Khu vực này dùng để xem và chỉnh sửa nội dung, timing và các dòng subtitle trong workflow thật.",
        "placement": "auto"
      },
      "safety": {
        "allow_back": false,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "ai_workspace_overview",
      "type": "INFO",
      "surface": { "route": "workspace", "subroute": "generate" },
      "anchor": "workspace.ai_generation",
      "target_policy": "FALLBACK_TO_INFO",
      "callout": {
        "title": "AI Workspace",
        "body": "Generate là nơi cấu hình workflow tạo subtitle. Tour chỉ giới thiệu giao diện, không tải model và không chạy Whisper.",
        "placement": "auto"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "generation_demo",
      "type": "DEMO",
      "surface": { "route": "workspace", "subroute": "generate" },
      "callout": {
        "title": "Minh họa workflow tạo subtitle",
        "body": "Đây là demo local được dựng sẵn. Không có model, CUDA, media thật hay tác vụ nền nào được khởi chạy.",
        "placement": "center"
      },
      "demo": {
        "asset": "assets/getting_started_generation.gif",
        "media_type": "gif",
        "fit": "contain"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "export_center_overview",
      "type": "INFO",
      "surface": { "route": "export_center" },
      "anchor": "export_center.root",
      "target_policy": "FALLBACK_TO_INFO",
      "callout": {
        "title": "Export Center",
        "body": "Export Center tập trung các lựa chọn xuất kết quả. Tour chỉ điều hướng tới trang này và không tạo file xuất.",
        "placement": "auto"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    },
    {
      "step_id": "finish",
      "type": "INFO",
      "callout": {
        "title": "Hoàn tất",
        "body": "Bạn đã xem các khu vực chính. Có thể mở Help Center để xem lại Getting Started bất cứ lúc nào.",
        "placement": "center"
      },
      "safety": {
        "allow_back": true,
        "allow_skip_step": true,
        "allow_skip_tour": true
      },
      "preconditions": []
    }
  ]
}
```

Do not add `TARGET`, `NAVIGATE`, executable fields, page indexes, raw Qt signals, or step-level Python expressions.

- [ ] **Step 4: Run the focused contract test and the existing catalog tests**

Run:

```bash
python -m unittest tests.test_c5_production_tour_contract tests.test_tour_catalog -v
```

Expected: PASS. Existing `test_production_catalog_loads` must still report only `getting_started`.

- [ ] **Step 5: Commit Task 1**

```bash
git add resources/tutorials/getting_started.json tests/test_c5_production_tour_contract.py
git commit -m "feat(tour): add C5 production getting started content"
```

---

### Task 2: Register exactly six production anchors at the MainWindow composition root

**Files:**
- Create: `tests/test_c5_production_anchor_bootstrap.py`
- Modify: `ui/Gui.py` around the sidebar New Project button, tutorial subsystem bootstrap, and helper-method area near `_start_tour_from_help()`.

**Interfaces:**
- Consumes: `AnchorRegistry.register(anchor_id: str, widget: QWidget)`, `NavigationAdapter.navigate(SurfaceSpec, session_id, generation, request_id)`, existing stable MainWindow widget attributes.
- Produces: `MainWindow._register_tour_anchors() -> None`, stable `self.btn_new_project`, and the six locked production anchor registrations.

- [ ] **Step 1: Write the failing anchor bootstrap tests**

Create `tests/test_c5_production_anchor_bootstrap.py`:

```python
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.tutorial.models import AnchorStatus, SurfaceSpec
from ui.Gui import MainWindow
from ui.tutorial.anchor_registry import AnchorRegistry


LOCKED_IDS = (
    "dashboard.root",
    "dashboard.new_project",
    "navigation.video_workspace",
    "workspace.subtitle_editor",
    "workspace.ai_generation",
    "export_center.root",
)


class TestC5ProductionAnchorBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.progress_dir = tempfile.TemporaryDirectory()
        progress_file = Path(self.progress_dir.name) / "tutorial_progress.json"
        self.register_calls = []
        original_register = AnchorRegistry.register

        def recording_register(registry, anchor_id, widget):
            self.register_calls.append((anchor_id, widget))
            return original_register(registry, anchor_id, widget)

        with patch.object(AnchorRegistry, "register", new=recording_register), patch(
            "ui.Gui.RuntimePaths.get_tutorial_progress_file", return_value=progress_file
        ):
            self.window = MainWindow(
                project_service=MagicMock(),
                media_import_service=MagicMock(),
                recovery_manager=MagicMock(),
            )
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.progress_dir.cleanup()

    def _wait_until(self, predicate, timeout=2.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for production UI state")

    def _navigate(self, surface, token):
        ready = []
        slot = lambda session, generation, request: ready.append(
            (session, generation, request)
        )
        self.window.tour_navigation.surface_ready.connect(slot)
        try:
            self.window.tour_navigation.navigate(
                surface,
                session_id=token,
                generation=1,
                request_id=f"{token}-request",
            )
            self._wait_until(lambda: bool(ready))
        finally:
            self.window.tour_navigation.surface_ready.disconnect(slot)

    def _assert_resolves_to(self, anchor_id, widget):
        resolution = self.window.tour_anchor_registry.resolve(anchor_id)
        self.assertEqual(resolution.status, AnchorStatus.RESOLVED)
        self.assertIs(
            self.window.tour_anchor_registry.get_widget(resolution.handle),
            widget,
        )

    def test_tc260_bootstrap_calls_register_for_exact_locked_mapping(self):
        self.assertEqual(
            [anchor_id for anchor_id, _ in self.register_calls],
            list(LOCKED_IDS),
        )
        mapping = dict(self.register_calls)
        self.assertIs(mapping["dashboard.root"], self.window.page_dashboard)
        self.assertIs(mapping["dashboard.new_project"], self.window.btn_new_project)
        self.assertIs(mapping["navigation.video_workspace"], self.window.nav_btns[1])
        self.assertIs(mapping["workspace.subtitle_editor"], self.window.sub_editor)
        self.assertIs(mapping["workspace.ai_generation"], self.window.generation_panel)
        self.assertIs(mapping["export_center.root"], self.window.page_export)

    def test_tc261_locked_anchors_resolve_on_their_production_surfaces(self):
        self._assert_resolves_to("dashboard.root", self.window.page_dashboard)
        self._assert_resolves_to("dashboard.new_project", self.window.btn_new_project)
        self._assert_resolves_to(
            "navigation.video_workspace", self.window.nav_btns[1]
        )

        self._navigate(SurfaceSpec("workspace"), "workspace")
        self._assert_resolves_to(
            "workspace.subtitle_editor", self.window.sub_editor
        )

        self._navigate(SurfaceSpec("workspace", "generate"), "generate")
        self._assert_resolves_to(
            "workspace.ai_generation", self.window.generation_panel
        )

        self._navigate(SurfaceSpec("export_center"), "export")
        self._assert_resolves_to("export_center.root", self.window.page_export)

    def test_tc262_legacy_example_ids_are_not_registered(self):
        for anchor_id in (
            "media.new_from_url",
            "workspace.video",
            "workspace.timeline",
            "generate.start",
            "context.editor",
            "export.softsub",
            "export.hardsub",
        ):
            with self.subTest(anchor_id=anchor_id):
                self.assertEqual(
                    self.window.tour_anchor_registry.resolve(anchor_id).status,
                    AnchorStatus.NOT_FOUND,
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python -m unittest tests.test_c5_production_anchor_bootstrap -v
```

Expected: FAIL because `self.btn_new_project` and `_register_tour_anchors()` do not exist and the production registry receives no six anchor registrations.

- [ ] **Step 3: Promote the New Project button to a stable MainWindow attribute**

In `ui/Gui.py`, change only the local reference:

```python
# Before
btn_new_project = self.create_side_action_button(
    "✨  Tạo Dự Án Mới", self.action_new_project
)
btn_new_project.setStyleSheet(...)
sidebar_layout.addWidget(btn_new_project)

# After
self.btn_new_project = self.create_side_action_button(
    "✨  Tạo Dự Án Mới", self.action_new_project
)
self.btn_new_project.setStyleSheet(...)
sidebar_layout.addWidget(self.btn_new_project)
```

Keep the existing stylesheet text and signal target byte-for-byte except for replacing the variable name.

- [ ] **Step 4: Add the minimal composition helper**

Add near `_start_tour_from_help()`:

```python
def _register_tour_anchors(self):
    bindings = (
        ("dashboard.root", self.page_dashboard),
        ("dashboard.new_project", self.btn_new_project),
        ("navigation.video_workspace", self.nav_btns[1]),
        ("workspace.subtitle_editor", self.sub_editor),
        ("workspace.ai_generation", self.generation_panel),
        ("export_center.root", self.page_export),
    )
    for anchor_id, widget in bindings:
        self.tour_anchor_registry.register(anchor_id, widget)
```

Do not move navigation or tutorial content into this method.

- [ ] **Step 5: Call the helper at the locked bootstrap seam**

Change this block:

```python
self._register_help_shortcuts()
self.tour_anchor_registry = AnchorRegistry()
self.tour_dialog_observer = DialogLifecycleObserver(self)
```

into:

```python
self._register_help_shortcuts()
self.tour_anchor_registry = AnchorRegistry()
self._register_tour_anchors()
self.tour_dialog_observer = DialogLifecycleObserver(self)
```

The helper must execute after all six widgets already exist and before any Tour observer/engine can resolve targets.

- [ ] **Step 6: Run focused anchor/navigation regression tests**

```bash
python -m unittest \
  tests.test_c5_production_anchor_bootstrap \
  tests.test_ui_tutorial_b1 \
  -v
```

Expected: PASS. Existing dynamic resolver tests remain unchanged; C5 itself registers only static production widgets.

- [ ] **Step 7: Commit Task 2**

```bash
git add ui/Gui.py tests/test_c5_production_anchor_bootstrap.py
git commit -m "feat(tour): register C5 production anchors"
```

---

### Task 3: Prove the real production ACTION click advances the Tour without consuming application navigation

**Files:**
- Create: `tests/test_c5_production_tour_integration.py`

**Interfaces:**
- Consumes: production `MainWindow`, real `TourEngine`, real `InteractionObserverAdapter`, real `MainWindowRouter`, production `getting_started` v2 and the six production anchors from Tasks 1–2.
- Produces: an end-to-end test helper that later zero-mutation testing reuses and a regression guard for Step 4.

- [ ] **Step 1: Create the production integration fixture and ACTION test**

Create `tests/test_c5_production_tour_integration.py`:

```python
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.tutorial.models import TourState
from ui.Gui import MainWindow


class TestC5ProductionTourIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.progress_dir = tempfile.TemporaryDirectory()
        progress_file = Path(self.progress_dir.name) / "tutorial_progress.json"
        self.project_service = MagicMock()
        self.media_import_service = MagicMock()
        self.recovery_manager = MagicMock()
        with patch(
            "ui.Gui.RuntimePaths.get_tutorial_progress_file", return_value=progress_file
        ):
            self.window = MainWindow(
                project_service=self.project_service,
                media_import_service=self.media_import_service,
                recovery_manager=self.recovery_manager,
            )
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        if self.window.tour_engine.is_running():
            self.window.tour_engine.cancel("TEST_CLEANUP")
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.progress_dir.cleanup()

    def _wait_until(self, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        step = self.window.tour_engine.current_step()
        self.fail(
            "Timed out; state=%r step=%r"
            % (
                self.window.tour_engine.state(),
                step.step_id if step else None,
            )
        )

    def _wait_step(self, step_id, state):
        self._wait_until(
            lambda: self.window.tour_engine.state() is state
            and self.window.tour_engine.current_step() is not None
            and self.window.tour_engine.current_step().step_id == step_id
        )

    def _start_from_first_run_banner(self):
        self.assertTrue(self.window.first_run_banner.isVisible())
        self.window.first_run_banner.start_btn.click()
        self._wait_step("welcome", TourState.SHOWING_INFO)

    def _reach_video_workspace_action(self):
        self._start_from_first_run_banner()
        self.window.tour_engine.next()
        self._wait_step("dashboard_overview", TourState.SHOWING_INFO)
        self.window.tour_engine.next()
        self._wait_step("create_project_entry", TourState.SHOWING_INFO)
        self.window.tour_engine.next()
        self._wait_step("open_video_workspace", TourState.WAITING_ACTION)

    def test_tc263_real_video_workspace_click_is_observed_and_not_consumed(self):
        self._reach_video_workspace_action()
        self.assertTrue(self.window.tour_interaction_observer.is_bound())
        self.assertEqual(self.window.stack.current_index, 0)

        QTest.mouseClick(
            self.window.nav_btns[1],
            Qt.MouseButton.LeftButton,
        )

        self._wait_step("subtitle_editor_overview", TourState.SHOWING_INFO)
        self.assertEqual(self.window.stack.current_index, 1)
        self.assertFalse(self.window.tour_interaction_observer.is_bound())
        self.assertFalse(
            self.window.tour_engine.current_step().safety.allow_back
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the production ACTION path test**

```bash
python -m unittest tests.test_c5_production_tour_integration.TestC5ProductionTourIntegration.test_tc263_real_video_workspace_click_is_observed_and_not_consumed -v
```

Expected after Tasks 1–2: PASS. If it fails inside a closed C1–C4 component, stop implementation and classify the failure before changing that component; do not patch `TourEngine` or `InteractionObserverAdapter` under C5.

- [ ] **Step 3: Run the existing interaction-observer and MainWindow navigation regression tests**

```bash
python -m unittest \
  tests.test_ui_tutorial_b1 \
  tests.test_ui_tutorial_b2 \
  tests.test_main_window_c2 \
  -v
```

Expected: PASS.

- [ ] **Step 4: Commit the production ACTION acceptance test**

```bash
git add tests/test_c5_production_tour_integration.py
git commit -m "test(tour): cover C5 production action path"
```

---

### Task 4: Enforce the zero-mutation contract and full safe-tour completion

**Files:**
- Modify: `tests/test_c5_production_tour_integration.py`

**Interfaces:**
- Consumes: the Task 3 fixture/helpers and production Tour path.
- Produces: a regression test that proves the full nine-step tour completes while Project/media/generation/export/recovery business operations remain untouched.

- [ ] **Step 1: Add a full-tour helper to the integration test class**

Add inside `TestC5ProductionTourIntegration`:

```python
def _complete_safe_tour(self):
    self._reach_video_workspace_action()

    QTest.mouseClick(
        self.window.nav_btns[1],
        Qt.MouseButton.LeftButton,
    )
    self._wait_step("subtitle_editor_overview", TourState.SHOWING_INFO)

    self.window.tour_engine.next()
    self._wait_step("ai_workspace_overview", TourState.SHOWING_INFO)

    self.window.tour_engine.next()
    self._wait_step("generation_demo", TourState.SHOWING_DEMO)

    self.window.tour_engine.next()
    self._wait_step("export_center_overview", TourState.SHOWING_INFO)
    self.assertEqual(self.window.stack.current_index, 4)

    self.window.tour_engine.next()
    self._wait_step("finish", TourState.SHOWING_INFO)
    self.assertEqual(self.window.stack.current_index, 4)

    self.window.tour_engine.next()
    self._wait_until(
        lambda: self.window.tour_engine.state() is TourState.COMPLETED
    )
```

- [ ] **Step 2: Add the zero-mutation/completion test**

Add:

```python
def test_tc264_full_safe_tour_completes_without_business_mutation(self):
    self.project_service.reset_mock()
    self.media_import_service.reset_mock()
    self.recovery_manager.reset_mock()

    self.window.subtitle_generation_service.start_generation = MagicMock()

    with patch.object(self.window, "_trigger_export_softsub") as soft_export, \
            patch.object(self.window, "_trigger_export_hardsub") as hard_export:
        self._complete_safe_tour()

    for method_name in (
        "create_project",
        "create_auto_project",
        "open_project",
        "save_project",
        "save_draft",
        "load_draft",
        "mark_dirty",
    ):
        getattr(self.project_service, method_name).assert_not_called()

    self.media_import_service.assert_not_called()
    self.recovery_manager.assert_not_called()
    self.window.subtitle_generation_service.start_generation.assert_not_called()
    soft_export.assert_not_called()
    hard_export.assert_not_called()

    progress = self.window.tour_progress_store.status("getting_started", 2)
    self.assertEqual(progress.status.value, "COMPLETED")
    self.assertEqual(progress.content_version, 2)
```

The `reset_mock()` calls occur after MainWindow construction so constructor-only setup does not pollute the business-mutation assertion.

- [ ] **Step 3: Add the content-version migration guard at the UI integration level**

Add:

```python
def test_tc265_old_v1_completion_is_not_v2_completion(self):
    self.window.tour_progress_store.mark_completed("getting_started", 1)
    status = self.window.tour_progress_store.status("getting_started", 2)
    self.assertEqual(status.status.value, "OUTDATED")
    self.assertFalse(
        self.window.tour_progress_store.is_completed("getting_started", 2)
    )
```

This does not change first-run policy; it only guards the reason C5 uses `content_version = 2`.

- [ ] **Step 4: Run the focused integration tests**

```bash
python -m unittest tests.test_c5_production_tour_integration -v
```

Expected: PASS. The DEMO step may instantiate `QMovie` before the final C5 asset is created, but this test does not claim visual animation validity; Task 5 and the manual/PyInstaller gates own asset validity/playback proof.

- [ ] **Step 5: Run progress and first-run regression tests**

```bash
python -m unittest \
  tests.test_tour_progress \
  tests.test_first_run_c2 \
  tests.test_main_window_c2 \
  -v
```

Expected: PASS. Do not change `evaluate_startup()` to make `OUTDATED` behave as first-run `NOT_STARTED`.

- [ ] **Step 6: Commit Task 4**

```bash
git add tests/test_c5_production_tour_integration.py
git commit -m "test(tour): enforce C5 zero mutation contract"
```

---

### Task 5: Register one production C4 scenario, generate the 16:9 GIF, and validate it

**Files:**
- Create: `tests/test_c5_demo_capture_content.py`
- Modify: `tools/demo_capture/cli.py` only inside `_get_registry()` and its local model imports.
- Create via C4 pipeline: `resources/tutorials/assets/getting_started_generation.gif`

**Interfaces:**
- Consumes: `DemoScenarioRegistry`, `CaptureScenario`, `CaptureTarget`, `CaptureScope.FULL_WINDOW`, `CaptureProfile`, `WaitVisibleAction`, `HoldAction`, `ClickAction`, `WaitSettledAction`, `OutputSpec`, `OutputFormat.GIF`, existing CLI `main()` and existing C4 runner/validator.
- Produces: `_get_registry().ids() == ("getting_started_generation",)` and a committed validated `getting_started_generation.gif`.

- [ ] **Step 1: Write the failing production C4 content tests**

Create `tests/test_c5_demo_capture_content.py`:

```python
import io
import unittest
from contextlib import redirect_stdout

from core.demo_capture.models import (
    CaptureScope,
    ClickAction,
    HoldAction,
    OutputFormat,
    WaitSettledAction,
    WaitVisibleAction,
)
from tools.demo_capture.cli import _get_registry, main


class TestC5DemoCaptureContent(unittest.TestCase):
    def test_tc266_registry_contains_exact_production_scenario(self):
        registry = _get_registry()
        self.assertEqual(registry.ids(), ("getting_started_generation",))

        scenario = registry.get("getting_started_generation")
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.target.scope, CaptureScope.FULL_WINDOW)
        self.assertIsNone(scenario.target.semantic_id)
        self.assertEqual(scenario.profile.window_size, (960, 540))
        self.assertEqual(scenario.profile.fps, 10)
        self.assertEqual(scenario.profile.output_scale, 1.0)
        self.assertEqual(scenario.profile.default_wait_timeout_ms, 3000)
        self.assertEqual(scenario.output.filename, "getting_started_generation.gif")
        self.assertEqual(scenario.output.format, OutputFormat.GIF)

    def test_tc267_scenario_uses_only_locked_safe_semantic_actions(self):
        scenario = _get_registry().get("getting_started_generation")
        actions = scenario.actions

        self.assertEqual(len(actions), 6)
        self.assertIsInstance(actions[0], WaitVisibleAction)
        self.assertEqual(actions[0].target, "navigation.video_workspace")
        self.assertIsInstance(actions[1], HoldAction)
        self.assertEqual(actions[1].duration_ms, 500)
        self.assertIsInstance(actions[2], ClickAction)
        self.assertEqual(actions[2].target, "navigation.video_workspace")
        self.assertIsInstance(actions[3], WaitVisibleAction)
        self.assertEqual(actions[3].target, "workspace.ai_generation")
        self.assertIsInstance(actions[4], WaitSettledAction)
        self.assertIsNone(actions[4].timeout_ms)
        self.assertIsInstance(actions[5], HoldAction)
        self.assertEqual(actions[5].duration_ms, 1500)

        used_targets = {
            action.target
            for action in actions
            if hasattr(action, "target")
        }
        self.assertLessEqual(
            used_targets,
            {
                "dashboard.root",
                "dashboard.new_project",
                "navigation.video_workspace",
                "workspace.subtitle_editor",
                "workspace.ai_generation",
                "export_center.root",
            },
        )

    def test_tc268_cli_list_preserves_existing_count_only_contract(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["list"])
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), "Listing 1 scenarios...")
        self.assertNotIn("getting_started_generation", output.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python -m unittest tests.test_c5_demo_capture_content -v
```

Expected: FAIL because `_get_registry()` currently returns `DemoScenarioRegistry([])`.

- [ ] **Step 3: Implement the single production scenario without changing C4 behavior**

Replace only `_get_registry()` in `tools/demo_capture/cli.py` with:

```python
def _get_registry():
    from core.demo_capture.models import (
        CaptureProfile,
        CaptureScenario,
        CaptureScope,
        CaptureTarget,
        ClickAction,
        HoldAction,
        OutputFormat,
        OutputSpec,
        WaitSettledAction,
        WaitVisibleAction,
    )
    from core.demo_capture.registry import DemoScenarioRegistry

    scenario = CaptureScenario(
        id="getting_started_generation",
        target=CaptureTarget(
            semantic_id=None,
            scope=CaptureScope.FULL_WINDOW,
            padding=0,
        ),
        profile=CaptureProfile(
            window_size=(960, 540),
            fps=10,
            output_scale=1.0,
            default_wait_timeout_ms=3000,
        ),
        actions=(
            WaitVisibleAction("navigation.video_workspace"),
            HoldAction(500),
            ClickAction("navigation.video_workspace"),
            WaitVisibleAction("workspace.ai_generation"),
            WaitSettledAction(),
            HoldAction(1500),
        ),
        output=OutputSpec(
            "getting_started_generation.gif",
            OutputFormat.GIF,
        ),
    )
    return DemoScenarioRegistry((scenario,))
```

Do not add `NavigateAction`, capture-only anchors, callbacks, or a second registry module.

- [ ] **Step 4: Run the registry/CLI tests and existing C4 CLI regression tests**

```bash
python -m unittest \
  tests.test_c5_demo_capture_content \
  tests.test_demo_capture_cli_c4 \
  -v
```

Expected: PASS. `list` still imports no `PySide6.QtWidgets` and still prints only the scenario count.

- [ ] **Step 5: Prove validation fails before the required asset is present**

If an old local file exists, remove only the C5 asset first:

PowerShell:

```powershell
Remove-Item "resources/tutorials/assets/getting_started_generation.gif" -Force -ErrorAction SilentlyContinue
python -m tools.demo_capture validate
```

Expected: exit code `3` and a validation message indicating the production GIF is missing. This RED proves the registry is now wired into the existing CI validator.

- [ ] **Step 6: Generate the asset through the existing C4 isolated pipeline**

On the development environment with PySide6/Pillow installed:

PowerShell:

```powershell
$env:QT_SCALE_FACTOR = "1"
python -m tools.demo_capture generate getting_started_generation
```

Expected: exit code `0`; final file exists at:

```text
resources/tutorials/assets/getting_started_generation.gif
```

Do not hand-author, download, or replace the final GIF outside the C4 pipeline.

- [ ] **Step 7: Validate the committed-asset contract and inspect its physical properties**

Run:

```powershell
python -m tools.demo_capture validate
python -c "from pathlib import Path; from PIL import Image; p=Path('resources/tutorials/assets/getting_started_generation.gif'); im=Image.open(p); assert im.format == 'GIF'; assert im.size == (960, 540); assert getattr(im, 'n_frames', 1) >= 2; total=0; [im.seek(i) or globals().update() for i in range(im.n_frames)]; print(p, im.size, im.n_frames, p.stat().st_size)"
```

Then run the validator-backed test directly:

```bash
python -m unittest tests.test_demo_capture_asset_validation_c4 -v
```

Expected:

- `python -m tools.demo_capture validate` exits `0` with `Validation passed.`
- GIF size is exactly `960x540` (16:9).
- GIF has at least 2 frames.
- Existing C4 validator enforces maximum 8 MiB, 200 frames, and 20 seconds.

- [ ] **Step 8: Visually inspect the generated GIF before committing**

Open `resources/tutorials/assets/getting_started_generation.gif` locally and confirm:

```text
initial Dashboard frame is readable
→ Video Workspace navigation visibly changes the production UI
→ final Workspace/AI generation context is readable
→ no Project dialog appears
→ no media/model/export workflow is shown as having actually run
→ no clipping or severe scaling artifact is present
```

If the asset is unclear, tune only the two `HoldAction` durations while preserving the exact semantic targets and all existing C4 limits; rerun Steps 4–8 after any duration change.

- [ ] **Step 9: Commit scenario, tests, and generated asset together**

```bash
git add \
  tools/demo_capture/cli.py \
  tests/test_c5_demo_capture_content.py \
  resources/tutorials/assets/getting_started_generation.gif
git commit -m "feat(capture): add C5 guided tour demo asset"
```

Do not leave a commit where the production registry references a missing asset.

---

### Task 6: Run the complete automated C5 and regression gates

**Files:**
- No production file changes are expected.
- Modify a test only if the failure proves the test itself contradicts the locked spec; do not weaken assertions to make the suite green.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: a verified implementation revision ready for human manual acceptance.

- [ ] **Step 1: Run all C5 tests together**

```bash
python -m unittest \
  tests.test_c5_production_tour_contract \
  tests.test_c5_production_anchor_bootstrap \
  tests.test_c5_production_tour_integration \
  tests.test_c5_demo_capture_content \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite in the same command used by CI**

```bash
python -m unittest discover -s tests -v
```

Expected: all tests PASS.

If the previously known PySide6 test-order isolation issue reproduces locally but the same revision passes isolated C5 tests, do not patch C5 architecture. Capture the exact failing order/output and classify it as the already-known test-isolation maintenance issue before any separate fix.

- [ ] **Step 3: Run compilation and demo-asset validation gates**

```bash
python -m compileall core ui workers tools tests
python -m tools.demo_capture validate
```

Expected: both commands exit `0`.

- [ ] **Step 4: Run whitespace/diff correctness checks**

```bash
git diff --check e0fbea153e889a6127e6d4403ae8fe343645b7d1...HEAD
git status --short
```

Expected:

```text
git diff --check → no output
working tree → clean
```

- [ ] **Step 5: Verify the C1–C4 closed-code boundary by changed-file list**

Run:

```bash
git diff --name-only e0fbea153e889a6127e6d4403ae8fe343645b7d1...HEAD
```

Expected implementation-related paths are limited to:

```text
docs/superpowers/specs/2026-09-10-c5-production-guided-tour-content-release-acceptance-design.md
docs/superpowers/plans/2026-09-10-c5-production-guided-tour-content-release-acceptance.md
ui/Gui.py
resources/tutorials/getting_started.json
tools/demo_capture/cli.py
resources/tutorials/assets/getting_started_generation.gif
tests/test_c5_production_tour_contract.py
tests/test_c5_production_anchor_bootstrap.py
tests/test_c5_production_tour_integration.py
tests/test_c5_demo_capture_content.py
```

The following path families must be absent unless a separately approved regression decision exists:

```text
core/tutorial/
ui/tutorial/
core/demo_capture/
ui/demo_capture/
```

- [ ] **Step 6: Do not create a verification-only commit**

If Steps 1–5 are clean and no files changed, keep the existing task commits unchanged. If a legitimate C5 test/content correction was required, rerun the affected RED/GREEN cycle and commit it with a specific message before continuing.

---

### Task 7: Execute the real production Manual Acceptance Gate

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes: automated-GREEN implementation revision from Task 6.
- Produces: human acceptance evidence for the real production path. This gate must run through `main.py`, not a direct `DemoMediaViewer` or custom Tour harness.

- [ ] **Step 1: Create a disposable Windows profile and launch the real app**

From the repository worktree in PowerShell:

```powershell
$C5Profile = Join-Path $PWD ".tmp\c5-manual-profile"
Remove-Item $C5Profile -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $C5Profile | Out-Null
$OldLocalAppData = $env:LOCALAPPDATA
$env:LOCALAPPDATA = $C5Profile
python main.py
```

Restore the environment after the manual session:

```powershell
$env:LOCALAPPDATA = $OldLocalAppData
```

Do not use the user's normal tutorial profile for acceptance.

- [ ] **Step 2: Verify C2 startup semantics before starting the tour**

On clean normal launch confirm all three:

```text
first-run banner is visible
Tour is NOT auto-started
no Recovery or external-open flow has been triggered
```

Then click the banner's Start action and confirm the banner disappears before the Tour begins.

- [ ] **Step 3: Accept Steps 1–4 exactly**

Check:

```text
Step 1 welcome:
  Dashboard visible
  centered callout
  no Project/media/model action

Step 2 dashboard_overview:
  Dashboard spotlight when resolvable
  content remains usable

Step 3 create_project_entry:
  New Project button highlighted
  do NOT click it
  no Project dialog opens

Step 4 open_video_workspace:
  Video Workspace button highlighted
  Next is not the completion mechanism
  click Video Workspace manually
  actual production page changes to Workspace
  Tour advances to Step 5
```

- [ ] **Step 4: Accept Steps 5–7 exactly**

Check:

```text
Step 5 subtitle_editor_overview:
  Subtitle Editor region targeted
  Back control cannot re-enter Step 4

Step 6 ai_workspace_overview:
  workspace/generate is prepared
  AI generation panel visible/targeted when resolvable
  no model load, CUDA initialization, or generation starts

Step 7 generation_demo:
  local GIF appears
  GIF visibly animates
  callout remains above DEMO media
  aspect ratio is correct
  no network/model/media/background workflow starts
  leaving the step hides/stops the viewer
```

- [ ] **Step 5: Accept Steps 8–9 and completion persistence**

Check:

```text
Step 8 export_center_overview:
  Tour automatically navigates to Export Center
  Export Center spotlight resolves or safely falls back to INFO
  no export dialog/file operation starts

Step 9 finish:
  Export Center remains current
  final callout appears
  final Next completes the Tour
```

Close and relaunch with the same disposable profile; confirm completion persists and first-run onboarding does not appear as `NOT_STARTED`.

- [ ] **Step 6: Verify manual replay**

Open Help Center and replay Getting Started.

Confirm:

```text
replay starts from welcome
all nine steps are available again
completion record is not downgraded/corrupted
next normal launch does not show first-run onboarding
```

- [ ] **Step 7: Clean the disposable profile only after acceptance evidence is captured**

```powershell
Remove-Item $C5Profile -Recurse -Force -ErrorAction SilentlyContinue
```

Any manual failure must be mapped to the owning contract before code changes. A failure in a locked C1–C4 runtime component is not automatically a C5 implementation fix.

---

### Task 8: Execute the Windows/PyInstaller release smoke gate

**Files:**
- No source changes expected.
- `build/ai_subtitle_studio.spec` must remain unchanged unless packaged smoke proves the existing whole-`resources/` packaging contract is broken and a separate decision approves a packaging fix.

**Interfaces:**
- Consumes: manual-GREEN source revision and existing PyInstaller spec.
- Produces: packaged-runtime proof that the bundled tutorial JSON/GIF and progress behavior work without source-tree fallback.

- [ ] **Step 1: Confirm the release environment is Python 3.11 and PyInstaller is already available**

```powershell
py -3.11 --version
py -3.11 -m PyInstaller --version
```

Expected: Python reports `3.11.x` and PyInstaller reports an installed version. If PyInstaller is absent, stop the release smoke; do not add an arbitrary new dependency/version to C5 to satisfy the local environment.

- [ ] **Step 2: Build from the real spec**

```powershell
py -3.11 -m PyInstaller --clean --noconfirm build/ai_subtitle_studio.spec
```

Expected: build exits `0` and produces the existing onedir distribution under:

```text
dist/AI Subtitle Studio/
```

- [ ] **Step 3: Verify the three required tutorial resources exist inside the distribution**

```powershell
$Dist = Join-Path $PWD "dist\AI Subtitle Studio"
Test-Path (Join-Path $Dist "resources\tutorials\catalog.json")
Test-Path (Join-Path $Dist "resources\tutorials\getting_started.json")
Test-Path (Join-Path $Dist "resources\tutorials\assets\getting_started_generation.gif")
```

Expected: all three commands print `True`.

Also inspect packaged JSON identity:

```powershell
py -3.11 -c "import json, pathlib; p=pathlib.Path(r'dist/AI Subtitle Studio/resources/tutorials/getting_started.json'); d=json.loads(p.read_text(encoding='utf-8')); assert d['guide_id']=='getting_started'; assert d['content_version']==2; assert len(d['steps'])==9; print('packaged tutorial contract OK')"
```

Expected: `packaged tutorial contract OK`.

- [ ] **Step 4: Launch the packaged EXE with a fresh disposable profile**

```powershell
$PackagedProfile = Join-Path $PWD ".tmp\c5-pyinstaller-profile"
Remove-Item $PackagedProfile -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $PackagedProfile | Out-Null
$OldLocalAppData = $env:LOCALAPPDATA
$env:LOCALAPPDATA = $PackagedProfile
& (Join-Path $Dist "AI Subtitle Studio.exe")
```

Do not run the source `main.py` during this smoke.

- [ ] **Step 5: Smoke the packaged nine-step path**

Confirm at minimum:

```text
EXE starts without source checkout resource fallback
Help Center loads getting_started v2
first-run banner behaves correctly
Step 1 renders
Step 4 accepts the real Video Workspace click
Step 6 reaches workspace/generate
Step 7 loads and animates the bundled GIF
Step 8 reaches Export Center
Step 9 completes
no network/model/CUDA/media/export requirement appears
```

- [ ] **Step 6: Prove packaged completion persistence**

Close the packaged app, launch the same EXE again with the same `$PackagedProfile`, and confirm onboarding is no longer treated as `NOT_STARTED`.

Then restore and clean:

```powershell
$env:LOCALAPPDATA = $OldLocalAppData
Remove-Item $PackagedProfile -Recurse -Force -ErrorAction SilentlyContinue
```

- [ ] **Step 7: Do not modify the PyInstaller spec if the smoke passes**

A passing smoke is explicit evidence that this existing block remains sufficient:

```python
resources_dir = os.path.join(project_root, 'resources')
if os.path.exists(resources_dir):
    datas.append((resources_dir, 'resources'))
```

No C5 packaging change is warranted when the existing contract works.

---

### Task 9: Final verification, review boundary, push, and CI gate

**Files:**
- No new implementation files expected.

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: final reviewable C5 branch revision with clean worktree and GREEN CI evidence.

- [ ] **Step 1: Run the complete final verification once more after manual/packaged acceptance**

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tools tests
python -m tools.demo_capture validate
git diff --check e0fbea153e889a6127e6d4403ae8fe343645b7d1...HEAD
```

Expected: all commands exit `0` and `git diff --check` prints nothing.

- [ ] **Step 2: Verify final branch contents and clean worktree**

```bash
git status --short
git log --oneline --decorate -10
git diff --name-only e0fbea153e889a6127e6d4403ae8fe343645b7d1...HEAD
```

Expected: `git status --short` is empty and the changed-file list obeys Task 6 Step 5.

- [ ] **Step 3: Push the implementation branch**

```bash
git push -u origin codex/c5-production-guided-tour
```

Expected: push succeeds without force.

- [ ] **Step 4: Require CI GREEN before C5 can be called complete**

The repository CI must execute its existing gates:

```text
unittest discover
compileall
demo capture asset validation
```

Do not close C5 on local/manual evidence alone.

- [ ] **Step 5: Review final diff against the locked spec before merge**

Reviewer must explicitly confirm:

```text
exactly six production anchor mappings
no register_resolver use in C5 production bootstrap
no new route/subroute
content_version == 2
exact nine-step order
only one ACTION
Step 4 REQUIRED + CLICK
five orientation anchors FALLBACK_TO_INFO
no guide/step preconditions
DEMO media_type == gif
C4 production registry exactly one scenario
committed validated 16:9 GIF
no closed C1–C4 component changes
manual acceptance PASS
PyInstaller smoke PASS
CI GREEN
```

Only after all items are satisfied should the normal repository PR/review/merge workflow be used to close C5.

---

## Self-Review Checklist for This Plan

Before execution, the plan author has checked:

```text
[covered] Spec §5 — exactly six production anchors and static register API
[covered] Spec §6 — getting_started identity + content_version 2
[covered] Spec §7–8 — exact nine-step JSON and ACTION/back fence
[covered] Spec §9 — no preconditions / no TourEngine precondition change
[covered] Spec §10 — gif media_type, relative asset path, 16:9 compatibility
[covered] Spec §11 — one C4 production scenario, no NavigateAction, no capture-only anchors
[covered] Spec §12 — existing dashboard/workspace/export navigation only
[covered] Spec §13 — REQUIRED vs FALLBACK_TO_INFO policies
[covered] Spec §14 — zero-mutation integration proof
[covered] Spec §15 — parser-backed JSON, anchor, ACTION, zero-mutation, C4 asset tests
[covered] Spec §16 — real production manual acceptance
[covered] Spec §17 — Windows/PyInstaller resource and runtime smoke
[covered] Spec §18 — M1–M5 handled without reopening C1–C4
[covered] Spec §21 — final suite/compileall/asset/manual/PyInstaller/CI/cleanliness gates
```

No `TBD`, `TODO`, fake route, placeholder callback, or unspecified implementation step is intentionally left in this plan.
