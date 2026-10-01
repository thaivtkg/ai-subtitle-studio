# Help Center + Interactive Guided Tour — Design Specification

**Trạng thái:** ✅ KIẾN TRÚC ĐÃ PHÊ DUYỆT TRONG REVIEW — CHỜ REVIEW FILE CUỐI  
**Ngày:** 2026-09-04  
**Nhánh:** `help-center-guided-tour-design`  
**Nền:** `master` sau Sprint 12 (`4fc21d2c1e4adc4ea19cbf6e34eadd8477c832ba`)

---

# 1. Mục tiêu

Thiết kế một phân hệ **Help Center + Interactive Guided Tour** chạy local/offline cho AI Subtitle Studio, giúp người dùng học workflow trực tiếp trên giao diện thật mà không làm tăng coupling vào `ui/Gui.py`, không kích hoạt các tác vụ nặng hoặc nguy hiểm chỉ để minh họa, và không can thiệp vào `ProjectState`, `RevisionTracker`, `RecoveryManager`, Worker hay pipeline AI/media.

Mô hình UX đã khóa là **Hybrid**:

- `INFO`: giải thích thuần túy, chuyển bước bằng Next/Back.
- `ACTION`: người dùng thao tác thật lên widget thật; Tour chỉ quan sát.
- `DEMO`: minh họa bằng asset local cho các bước nặng/nguy hiểm như download, Whisper hoặc ghi dữ liệu.

Ba nguyên tắc trung tâm:

> Tour chỉ hướng dẫn và quan sát; Tour không phải transaction của ứng dụng và không sở hữu business state.

> Scenario chỉ mô tả semantic intent; không chứa executable code, raw Qt signal name, callback hay page/tab index.

> Help/Tour subsystem có thể lỗi hoặc thiếu tài nguyên mà không được làm hỏng startup, Project hay workflow chính.

---

# 2. Ngoài phạm vi

Phân hệ này **không** bao gồm:

- Tự động chạy Whisper, media download, hardsub/export thật để minh họa.
- Tự tạo Project, tự load media hoặc tự sửa business state để thỏa precondition.
- Rollback thao tác người dùng khi Tour bị hủy.
- Persist trạng thái mid-tour/current step trong schema v1.
- Telemetry, analytics hoặc gửi dữ liệu ra mạng.
- Remote help content hoặc remote tutorial assets.
- Auto-fix troubleshooting.
- Command bus/event-bus rewrite toàn ứng dụng.
- Macro recorder/replay.
- Editable keyboard shortcuts.
- MP4/video-codec pipeline riêng cho tutorial.
- Cryptographic asset manifest không ký.
- Fullscreen synthetic mouse forwarding hoặc `sendEvent()` để giả click.

---

# 3. Kiến trúc nền tảng đã khóa

Phương án được chọn:

```text
TourEngine
   ├─ TourCatalog / TourDefinition
   ├─ AnchorRegistry
   ├─ NavigationAdapter
   ├─ InteractionObserver
   ├─ SpotlightLayer
   ├─ DialogLifecycleObserver
   ├─ TourEnvironment
   └─ TourProgressStore

HelpCenterPage
   ├─ HelpCatalog
   ├─ GuideCatalogWidget
   ├─ Article / FAQ / Shortcut views
   ├─ HelpCenterController
   └─ FirstRunPolicy / FirstRunBanner
```

Package boundary đề xuất:

```text
core/tutorial/
├─ models.py
├─ catalog.py
├─ ports.py
├─ tour_engine.py
├─ progress_store.py
└─ environment.py

core/help/
├─ help_catalog.py
├─ help_models.py
└─ first_run_policy.py

ui/tutorial/
├─ anchor_registry.py
├─ navigation_adapter.py
├─ interaction_observer.py
├─ spotlight_layer.py
├─ dialog_lifecycle_observer.py
└─ widgets/
   ├─ tour_callout.py
   └─ demo_media_viewer.py

ui/help/
├─ help_center_page.py
├─ help_center_controller.py
├─ guide_catalog_widget.py
├─ guide_card.py
├─ article_viewer.py
├─ shortcut_view.py
├─ faq_view.py
└─ first_run_banner.py

resources/help/
├─ catalog.json
├─ faq.json
└─ articles/

resources/tutorials/
├─ catalog.json
├─ *.json
└─ assets/
```

`MainWindow` chỉ đóng vai trò composition root: tạo subsystem, gọi bootstrap đăng ký anchor, thêm Help Center page, wire Help action/F1. Không được chứa state machine hoặc cờ tutorial theo step.

---

# 4. Section 1 — Data Contract / JSON Scenario Schema

## 4.1. Guide contract

```json
{
  "schema_version": 1,
  "guide_id": "import_url",
  "content_version": 1,
  "title": "Import video từ URL",
  "description": "Tải media về local và đưa vào Project hoặc Queue.",
  "category": "media",
  "estimated_minutes": 2,
  "steps": []
}
```

Quy tắc:

- `schema_version`: version của DSL.
- `guide_id`: immutable semantic ID; không dùng title làm identity.
- `content_version`: tăng khi workflow/nội dung guide thay đổi đủ để invalid completion cũ.
- `steps`: ordered list, được parse thành immutable runtime snapshot.
- `guide_id + content_version` là learning identity và không thuộc `ProjectState`.

## 4.2. Step types

Enum v1 chỉ gồm:

```text
INFO
ACTION
DEMO
```

Shape chung:

```json
{
  "step_id": "open_url_import",
  "type": "ACTION",
  "surface": { "route": "dashboard" },
  "anchor": "media.new_from_url",
  "target_policy": "REQUIRED",
  "callout": {
    "title": "Import từ URL",
    "body": "Nhấn nút này để mở cửa sổ nhập URL.",
    "placement": "auto"
  },
  "interaction": { "kind": "CLICK" },
  "safety": {
    "allow_back": false,
    "allow_skip_step": true,
    "allow_skip_tour": true
  }
}
```

## 4.3. Surface inheritance

`surface` là optional.

- Có `surface`: `PREPARING_SURFACE` yêu cầu `NavigationAdapter` điều hướng.
- Không có `surface`/`null`: giữ surface hiện tại và không gọi adapter.

Scenario không được chứa `page_index`, `tab_index` hoặc số index implementation.

Semantic route v1 dự kiến:

```text
dashboard
workspace
queue
draft_center
export_center
settings
help
```

Semantic subroute ví dụ:

```text
workspace/generate
workspace/context
workspace/style
workspace/log
```

## 4.4. Anchor contract

Scenario chỉ chứa semantic anchor ID:

```text
media.new_from_url
media.add_url_queue
workspace.video
workspace.timeline
generate.start
context.editor
queue.list
export.softsub
export.hardsub
```

Không lưu objectName, widget path hay pixel coordinate trong JSON.

`AnchorRegistry` hỗ trợ:

- static guarded reference;
- dynamic resolver;
- objectName fallback nội bộ nếu cần, nhưng objectName không phải contract của scenario.

## 4.5. Interaction contract

JSON mô tả ý định, không mô tả Qt implementation:

```text
CLICK
FOCUS
TEXT_COMMITTED
SELECTION_CHANGED
DIALOG_ACCEPTED
```

Cấm schema chứa raw Qt signal name, callback hoặc executable expression.

`ACTION` không bao giờ được gọi Worker/Service hoặc tự chạy business command. Người dùng phải thực hiện action thật.

`allow_back` mặc định:

- `INFO`: true.
- `DEMO`: true.
- `ACTION`: false.
- `ACTION + FOCUS`: có thể explicit true vì không gây state mutation đáng kể.

## 4.6. Callout placement

Enum khóa cứng:

```text
auto
top
bottom
left
right
center
```

`auto` tính vùng trống quanh bounding box của anchor, ưu tiên hướng fit hoàn toàn; nếu không fit thì chọn candidate tốt nhất rồi clamp vào viewport.

## 4.7. Missing anchor policy

```text
REQUIRED
FALLBACK_TO_INFO
SKIP
```

- `REQUIRED`: vào `RECOVERING`.
- `FALLBACK_TO_INFO`: bỏ spotlight, giữ callout và cho Next.
- `SKIP`: tự advance.

Mặc định: `FALLBACK_TO_INFO`.

## 4.8. Preconditions

Scenario dùng semantic requirement, không dùng Python expression:

```text
PROJECT_OPEN
MEDIA_LOADED
NO_BACKGROUND_JOB
```

`TourEnvironment` chỉ đọc trạng thái hiện tại. Nếu thiếu precondition, Help Center giải thích requirement; Tour không mutate app để tự thỏa điều kiện.

## 4.9. Demo contract

DEMO chỉ tham chiếu asset local đã confinement dưới `resources/tutorials/assets/`.

Baseline v1:

```text
IMAGE
ANIMATED_IMAGE
```

Animation bắt buộc hỗ trợ: GIF. Animated WebP chỉ được phép nếu packaged-runtime characterization chứng minh có plugin và multi-frame playback hoạt động.

## 4.10. Validation

`TourCatalog` phải reject guide/step nếu có ít nhất một lỗi sau:

- duplicate `guide_id` / `step_id`;
- unknown step type;
- unknown route/subroute;
- unknown interaction kind;
- ACTION thiếu anchor/interaction;
- DEMO thiếu asset;
- INFO chứa interaction;
- asset path thoát resource root;
- empty steps;
- unsupported schema version;
- executable/callback/raw-signal field không được phép.

Một guide invalid không được làm hỏng các guide valid khác.

---

# 5. Section 2 — TourEngine State Machine

## 5.1. Runtime states

```text
IDLE
PREPARING_SURFACE
RESOLVING_TARGET
SHOWING_INFO
WAITING_ACTION
SHOWING_DEMO
ADVANCING_STEP
RECOVERING
COMPLETED
CANCELLED
```

Happy path:

```text
IDLE
 → PREPARING_SURFACE
 → RESOLVING_TARGET
 → SHOWING_INFO | WAITING_ACTION | SHOWING_DEMO
 → ADVANCING_STEP
 → next step hoặc COMPLETED
```

Bất kỳ active state nào đều có đường thoát an toàn tới `CANCELLED`.

## 5.2. Transition contract chính

- Chỉ `PREPARING_SURFACE` được gọi `NavigationAdapter`.
- `surface == null`: đi thẳng sang `RESOLVING_TARGET`.
- same-surface: adapter emit ready bằng `QTimer.singleShot(0, ...)`, không đợi animation signal.
- changed-surface: chỉ ready khi page/subroute thực sự ổn định.
- `WAITING_ACTION`: chỉ advance sau khi interaction thỏa.
- ACTION acknowledgement synchronous; prepare step tiếp theo **luôn queued** bằng event-loop tick mới.
- `ADVANCING_STEP` là transaction boundary giữa hai step.
- `cleanup_step_scope()` phải idempotent.

## 5.3. Session / generation guards

Mỗi Tour có:

```text
tour_session_id
step_generation
navigation_request_id
```

Mọi async callback phải capture token và trở thành no-op nếu session/generation/request không còn current.

Late signal từ animation, dialog hoặc old step không được phép thay state mới.

## 5.4. WAITING_ACTION lifecycle

Entry:

1. Validate target lần cuối.
2. Attach Spotlight.
3. Bind `InteractionObserver`.
4. Connect target lifecycle.
5. Enter `WAITING_ACTION`.

Rời state bằng bất kỳ đường nào phải unbind observer:

- action success;
- Skip Step;
- Skip Tour / Esc;
- Back nếu được phép;
- target destroyed;
- dialog closed;
- exception/recovery;
- app shutdown.

`unbind()` idempotent và không dereference dead C++ object.

## 5.5. Non-consuming observation

Khi `InteractionObserver.eventFilter()` thấy interaction hợp lệ, observer chỉ witness và **trả `False`**.

Không gọi `accept()`, không synthetic click, không `sendEvent()`.

Mục tiêu: widget thật tiếp tục nhận event và business `clicked()`/focus/change logic chạy bình thường.

## 5.6. Modal QDialog

`QDialog.exec()` block caller stack nhưng chạy nested Qt event loop, vì vậy Tour vẫn nhận signal/QTimer/event filter.

Flow bắt buộc cho action mở dialog:

```text
Mouse release/action satisfied
→ detach observer
→ queue next preparation
→ business clicked slot chạy
→ dialog.exec() tạo nested event loop
→ queued callback chạy
→ dynamic resolver tìm widget trong dialog
→ Spotlight chuyển host MainWindow → QDialog
```

Khi modal đang active, Tour **không cướp phím Esc** bằng global shortcut. Qt cho QDialog xử lý Esc/reject; `DialogLifecycleObserver` nhận `finished(Rejected)` và Tour áp dụng `target_policy`.

## 5.7. Recovery

`RECOVERING` dùng Tour Callout không-blocking với:

```text
Retry
Skip Step
End Tour
```

Retry chỉ resolve lại target/surface; không tự click hay tự chạy business action.

Không auto-retry vô hạn.

## 5.8. Watchdogs

```text
NAVIGATION_TIMEOUT_MS = 2500
TARGET_SETTLE_TIMEOUT_MS = 750
```

Timeout phải injectable trong tests.

Target settle là event-driven; không polling tight loop.

---

# 6. Section 3 — Component Interfaces & Responsibilities

## 6.1. TourEngine

`TourEngine(QObject)` được phép import duy nhất Qt core cần thiết (`QObject`, `Signal`, `Slot`, `QTimer`). Cấm import `PySide6.QtWidgets` hoặc `PySide6.QtGui` trong `core/tutorial/tour_engine.py`.

Nó sở hữu:

- current session;
- immutable guide snapshot;
- current step/index;
- TourState;
- generation/request tokens;
- transition sequencing;
- policy handling;
- completion/cancellation.

Nó không sở hữu QWidget/QDialog, business service, ProjectState hay Worker.

Public API conceptual:

```python
class TourEngine(QObject):
    state_changed = Signal(object)
    tour_started = Signal(str)
    step_changed = Signal(str, str, int, int)
    tour_completed = Signal(str)
    tour_cancelled = Signal(str, str)

    def start(self, guide_id: str) -> bool: ...
    def next(self) -> None: ...
    def back(self) -> None: ...
    def skip_step(self) -> None: ...
    def retry(self) -> None: ...
    def cancel(self, reason: str = "USER_CANCELLED") -> None: ...
```

## 6.2. AnchorRegistry

Conceptual API:

```python
register(anchor_id, widget)
register_resolver(anchor_id, resolver)
unregister(anchor_id)
resolve(anchor_id) -> AnchorResolution
clear()
```

Static reference không tạo ownership mới. Resolve phải guard bằng weak reference + `shiboken6.isValid()`.

`AnchorStatus`:

```text
RESOLVED
NOT_FOUND
INVALID
NOT_VISIBLE
```

Anchor trong dialog đã `finished()` phải được coi là inactive dù C++ object chưa destroy.

## 6.3. NavigationAdapter

`MainWindowNavigationAdapter` là nơi duy nhất biết semantic route → UI implementation mapping.

Conceptual API:

```python
navigate(surface, *, session_id, generation, request_id)
current_surface()
cancel_pending()
```

Signals:

```text
surface_ready(session, generation, request)
surface_failed(session, generation, request, reason)
```

`AnimatedStack` được bổ sung public generic signal:

```python
transition_finished = Signal(int)
```

Signal này không mang tutorial semantics; nó expose lifecycle transition hiện có.

Subroute chỉ ready sau khi dock/tab/drawer đã ổn định, không dùng magic sleep.

## 6.4. InteractionObserver

Conceptual API:

```python
bind(anchor, interaction, *, session_id, generation)
unbind()
is_bound()
eventFilter(watched, event) -> bool
```

Responsibilities:

- observe interaction;
- emit action satisfied/target lost;
- remove filter + disconnect signal handles an toàn;
- luôn non-consuming với action được quan sát.

## 6.5. SpotlightLayer

Hole-cutout vật lý bằng bốn vùng tối:

```text
DimTop
DimBottom
DimLeft
DimRight
SpotlightBorder
TourCallout
```

Không có transparent widget che phần target, do đó mouse rơi tự nhiên xuống widget thật.

Một SpotlightLayer chỉ có tối đa một active host: MainWindow hoặc active QDialog.

Conceptual API:

```python
attach_host(host)
detach_host()
show_target(anchor, callout, controls)
show_info_without_target(callout, controls)
show_demo(demo, callout, controls)
show_recovery(message, retry_enabled, skip_enabled)
hide_step()
```

Border phải transparent for mouse. Dim regions ngoài target có thể consume interaction để hạn chế user thao tác ngoài step.

## 6.6. DialogLifecycleObserver

Quan sát top-level dialog chỉ trong lifetime Tour session.

Kết nối cả:

```text
QDialog.finished
QObject.destroyed
```

Ngay khi `finished` emit, `DialogHandle` phải chuyển `inactive` để ngăn zombie dialog anchor được resolve lại.

Signals semantic:

```text
dialog_shown(dialog_id)
dialog_finished(dialog_id, result)
dialog_destroyed(dialog_id)
modal_active_changed(bool)
```

## 6.7. TourProgressStore

Lưu user-learning state độc lập Project:

```text
%LOCALAPPDATA%/AI Subtitle Studio/tutorial_progress.json
```

Không dùng `settings.json`, không dirty Project, không Revision/Recovery.

Conceptual API:

```python
is_completed(guide_id, content_version)
mark_completed(guide_id, content_version)
mark_dismissed(guide_id, content_version)
status(guide_id, content_version)
reset(guide_id=None)
```

Schema v1 không persist current step.

## 6.8. TourEnvironment

Read-only semantic precondition checker:

```python
check(precondition: str) -> bool
```

Cấm method tạo/sửa app state.

---

# 7. Section 4 — Help Center & Guided Tour UX

## 7.1. Help Center là application page

Help Center là page chính thức trong `AnimatedStack`, không phải modal/dock.

Entry points:

```text
Sidebar → ❓ Help Center
F1 → Help Center
```

F1 không tự start Tour.

Help Center nội bộ gồm:

```text
Home
Guided Tours
User Guide
Keyboard Shortcuts
FAQ
Troubleshooting
```

Application route chỉ cần `help`; subsection do `HelpCenterPage` tự quản.

## 7.2. Home layout

V1 gồm:

- Help Search;
- Getting Started CTA;
- chủ đề chính;
- Guided Tour progress;
- troubleshooting/FAQ shortcuts.

Search local/offline, debounce mặc định `175 ms` (chấp nhận 150–200 ms).

Search index metadata:

- guide title/description;
- article title/keywords;
- FAQ question.

Không cần full-text engine hoặc online search.

## 7.3. Guide Catalog presentation

Card hiển thị:

- category badge;
- title/description;
- estimated minutes/step count;
- progress state;
- CTA.

CTA mapping:

```text
NOT_STARTED  → Hướng dẫn trực tiếp
COMPLETED    → Xem lại
DISMISSED    → Bắt đầu hướng dẫn
OUTDATED     → Xem nội dung mới
PRECONDITION_FAILED → Xem yêu cầu
```

Không disable mơ hồ.

## 7.4. Shortcut page

Shortcut key sequence lấy từ runtime `QShortcut`/provider, không duplicate hard-coded sequence trong docs để tránh documentation drift.

Không hỗ trợ chỉnh shortcut trong scope v1.

## 7.5. First-run policy

Không auto-start Tour.

First clean interactive launch chỉ hiển thị lời mời nhỏ ở đầu Dashboard:

```text
[Bắt đầu hướng dẫn] [Để sau]
```

Banner không-blocking, tự hide nếu user bắt đầu workflow thật từ đường khác.

Eligibility yêu cầu:

- getting_started chưa COMPLETED;
- chưa DISMISSED;
- normal interactive launch;
- không external-open Project/file association;
- không Recovery startup;
- MainWindow initialization xong;
- không startup modal active.

Priority:

```text
RECOVERY > EXTERNAL OPEN > ONBOARDING
```

`SUPPRESS` không đồng nghĩa `DISMISSED`.

Persistence semantics:

- banner chỉ hiện: progress unchanged;
- `Để sau`/explicit close: mark DISMISSED;
- Start first-run Tour: mark DISMISSED **trước** khi start;
- Tour complete: overwrite thành COMPLETED;
- workflow khác làm banner auto-hide: không ghi DISMISSED.

Manual Tour từ Help Center bị cancel không ghi DISMISSED.

## 7.6. DemoMediaViewer

Component nhẹ, không dùng VideoPlayer/GPU pipeline.

Static:

```text
QPixmap / QImageReader
```

Animated baseline:

```text
QMovie + GIF
```

Lifecycle:

```text
SHOWING_DEMO → load/start
leave step → stop
cleanup → clear/setMovie(None)
```

Demo asset failure fallback text-only và không fail Tour.

Authoring guideline:

- khoảng ≤ 960×540;
- loop ngắn ~10–15s;
- không audio;
- không MP4/MOV;
- lazy-load đúng asset của current DEMO step;
- không global animation cache.

Animated WebP là optional capability, chỉ bật sau package characterization.

---

# 8. Section 5 — Error Handling & Fault Tolerance

## 8.1. Fault classes

```text
CONTENT_FAULT
STEP_RUNTIME_FAULT
PRESENTATION_FAULT
PERSISTENCE_FAULT
PACKAGING_FAULT
```

Internal diagnostic codes:

```text
INVALID_GUIDE
UNSUPPORTED_GUIDE_SCHEMA
INVALID_ASSET_PATH
NAVIGATION_FAILED
NAVIGATION_TIMEOUT
ANCHOR_NOT_FOUND
ANCHOR_INVALID
ANCHOR_NOT_VISIBLE
TARGET_LOST
INTERACTION_BIND_FAILED
DIALOG_CLOSED
DEMO_ASSET_MISSING
DEMO_ASSET_UNSUPPORTED
DEMO_DECODE_FAILED
PROGRESS_CORRUPT
PROGRESS_UNSUPPORTED_SCHEMA
PROGRESS_WRITE_FAILED
RESOURCE_CATALOG_MISSING
RESOURCE_CATALOG_INVALID
```

Không code lỗi nào được làm Project dirty hoặc crash MainWindow nếu có thể degrade an toàn.

## 8.2. Fault responses

- guide invalid → disable guide đó, giữ guide valid khác;
- navigation fail/timeout → `RECOVERING`;
- missing anchor → áp target policy;
- dead pointer → `INVALID`, không dereference;
- dialog reject → inactive handle + policy/recovery;
- GIF missing/decode fail → text-only;
- corrupt progress → quarantine + empty progress;
- future progress schema → read-only unsupported;
- tutorial resources missing → disable Guided Tour, Help khác vẫn hoạt động;
- unexpected Tour exception → full Tour cleanup + CANCELLED + log.

## 8.3. Logging

Log semantic context như guide/step/state/error code, không log dữ liệu không cần thiết như URL user nhập hoặc private project path.

Không telemetry/network.

---

# 9. Persistence Specification

## 9.1. Canonical schema v1

```json
{
  "schema_version": 1,
  "updated_at": "2026-09-04T04:00:00+07:00",
  "guides": {
    "getting_started": {
      "content_version": 1,
      "status": "COMPLETED",
      "completed_at": "2026-09-04T03:58:00+07:00"
    },
    "import_url": {
      "content_version": 2,
      "status": "DISMISSED",
      "dismissed_at": "2026-09-04T03:59:00+07:00"
    }
  }
}
```

Persisted status v1 chỉ gồm `COMPLETED` và `DISMISSED`.

Không persist `IN_PROGRESS`, step index, UI geometry, dialog ID hoặc anchor.

## 9.2. schema_version rules

- stored == supported: normal read/write.
- stored < supported: migrate in memory; không rewrite chỉ vì read/startup; canonical rewrite khi có explicit mutation.
- stored > supported: `READ_ONLY_UNSUPPORTED`; không overwrite/downgrade future file. Tour vẫn chạy, progress query trả unknown/readonly semantics.

## 9.3. content_version rules

- stored == current: normal status.
- stored < current: `OUTDATED`, UI hiện "Có nội dung mới".
- stored > current: app downgrade; không hạ stored version và không nag onboarding.

## 9.4. Atomic write

Bắt buộc:

```text
candidate snapshot
→ tutorial_progress.json.tmp.<pid>.<uuid>
→ write
→ flush
→ os.fsync(file)
→ close
→ os.replace(temp, canonical)
→ publish candidate snapshot
```

Temp nằm cùng directory.

Nếu replace/write fail:

- canonical cũ giữ nguyên;
- cleanup temp best-effort;
- in-memory committed snapshot giữ bản cũ;
- log `PROGRESS_WRITE_FAILED`.

## 9.5. Corrupt recovery

Nếu JSON/type/schema bị corrupt:

```text
tutorial_progress.json
→ tutorial_progress.corrupt.<timestamp>.json
→ return empty progress
```

Nếu quarantine rename fail: chuyển `READ_ONLY_CORRUPT`, không overwrite evidence.

App startup không bị block.

---

# 10. Packaging Specification

## 10.1. Resource layout

Packaged runtime phải có:

```text
_internal/resources/
├─ help/
│  ├─ catalog.json
│  ├─ faq.json
│  └─ articles/*.md
└─ tutorials/
   ├─ catalog.json
   ├─ *.json
   └─ assets/*.{png,gif,webp}
```

Mọi resource lookup đi qua `RuntimePaths.get_resources_dir()`/resource abstraction; không hardcode `_MEIPASS` trong Help/Tour code.

## 10.2. PyInstaller data requirement

Spec phải bundle:

```text
resources/help → resources/help
resources/tutorials → resources/tutorials
```

Allowlist content:

```text
.json
.md
.png
.gif
.webp
```

Không bundle source design assets hoặc media nặng:

```text
.psd
.blend
.aep
.mp4
.mov
.tmp
.bak
```

## 10.3. Referential integrity gate

Build/test phải xác minh:

- catalog/guide JSON parse được;
- mọi referenced article/asset tồn tại;
- asset confinement đúng root;
- GIF baseline load được;
- critical reference không orphan.

Không thêm unsigned SHA manifest ở v1.

## 10.4. GIF / WebP gate

GIF là baseline bắt buộc.

Package smoke phải kiểm chứng:

```text
QMovie(test.gif).isValid() == True
frameChanged thực sự emit
```

Animated WebP chỉ enabled nếu packaged app chứng minh multi-frame playback hoạt động; không guide production nào được phụ thuộc duy nhất animated WebP.

---

# 11. Các invariant đã khóa

## INV-01 đến INV-12 — State / lifecycle

```text
INV-01  Chỉ TourEngine được thay current_step_index.
INV-02  WAITING_ACTION luôn có đúng một InteractionObserver binding.
INV-03  Rời WAITING_ACTION → binding phải bằng zero.
INV-04  IDLE/COMPLETED/CANCELLED → không có tutorial eventFilter.
INV-05  Chỉ PREPARING_SURFACE được gọi NavigationAdapter.
INV-06  TourEngine không gọi business Service/Worker.
INV-07  ACTION completion không prepare next step synchronously.
INV-08  Mọi async callback có session/generation guard.
INV-09  Spotlight chỉ attach top-level window chứa current target.
INV-10  Dead Qt pointer không được dereference sau validation failure.
INV-11  Esc luôn có đường đưa Tour về CANCELLED khi không bị modal ưu tiên xử lý.
INV-12  cleanup_step_scope() phải idempotent.
```

## INV-13 đến INV-20 — Component boundary

```text
INV-13  InteractionObserver không consume user event hợp lệ.
INV-14  AnchorRegistry không sở hữu QWidget bằng strong ownership contract.
INV-15  TourEngine không dereference Qt UI object.
INV-16  NavigationAdapter là nơi duy nhất biết semantic route → UI mapping.
INV-17  Một SpotlightLayer tối đa một active host.
INV-18  Khi modal active, Tour không intercept Esc trước QDialog.
INV-19  TourProgressStore không mutate ProjectState/Revision/Recovery.
INV-20  Schema v1 không persist mid-tour ACTION state.
```

## INV-21 đến INV-30 — Help/UX

```text
INV-21  Help Center không mutate ProjectState.
INV-22  Help/FAQ/Tour assets là local packaged resources.
INV-23  Help Center không gọi business Worker/Service để minh họa.
INV-24  First-run không auto-start Guided Tour; user phải xác nhận.
INV-25  External-open và Recovery startup ưu tiên hơn onboarding.
INV-26  Suppressed onboarding không đồng nghĩa DISMISSED.
INV-27  DISMISSED không ngăn manual replay từ Help Center.
INV-28  Demo asset failure không được fail/cancel Tour.
INV-29  Animated media stop/release khi rời DEMO step.
INV-30  Help/Tour không duplicate page/tab index hoặc raw Qt signal trong scenario.
```

## INV-31 đến INV-40 — Fault/persistence/packaging

```text
INV-31  Một guide/content fault không disable toàn Help Center.
INV-32  Navigation luôn bounded watchdog; không chờ surface vô hạn.
INV-33  Canonical progress chỉ thay sau temp write + fsync thành công.
INV-34  Unsupported future progress schema không bị overwrite.
INV-35  Corrupt progress không ngăn app startup.
INV-36  Packaged resources chỉ truy cập qua RuntimePaths/resource abstraction.
INV-37  GIF là animated baseline bắt buộc của v1.
INV-38  Animated WebP không phải dependency bắt buộc.
INV-39  Presentation/media failure không fail business workflow; text fallback được ưu tiên.
INV-40  Help/Tour failure không dirty Project, RevisionTracker hoặc Recovery.
```

---

# 12. Acceptance Test Matrix — TC132 đến TC193

| TC | Layer | Acceptance |
|---|---|---|
| TC132 | Unit | valid Tour JSON parse thành immutable `TourDefinition` |
| TC133 | Unit | optional `surface` kế thừa surface trước |
| TC134 | Unit | ACTION mặc định `allow_back=false`; INFO/DEMO back được |
| TC135 | Unit | placement chỉ nhận `auto/top/bottom/left/right/center` |
| TC136 | Unit | reject executable fields/unknown interaction/raw signal injection |
| TC137 | Unit | reject asset `../` hoặc thoát tutorial resource root |
| TC138 | Unit | một guide invalid không làm hỏng guide valid khác |
| TC139 | Qt component | static AnchorRegistry resolve widget valid |
| TC140 | Qt component | dynamic resolver resolve dialog widget |
| TC141 | Qt component | deleted C++ widget → `INVALID`, không RuntimeError |
| TC142 | Qt component | hidden/zombie dialog anchor không `RESOLVED` |
| TC143 | Event loop | same surface → queued `surface_ready`, không chờ animation |
| TC144 | Event loop | changed surface ready sau `transition_finished`/subroute settled |
| TC145 | Event loop | stale navigation request token bị ignore |
| TC146 | Event loop | navigation watchdog → `RECOVERING` |
| TC147 | Unit/Event | missing anchor áp đúng REQUIRED/FALLBACK/SKIP |
| TC148 | Event loop | CLICK observer witness event nhưng trả `False` |
| TC149 | Event loop | widget business `clicked()` vẫn chạy đúng một lần |
| TC150 | Qt component | bind/unbind eventFilter idempotent |
| TC151 | Event loop | target destroyed trong WAITING_ACTION cleanup không dereference |
| TC152 | Event loop | ACTION completion detach observer trước advance |
| TC153 | Event loop | next ACTION step prepare ở event-loop tick tiếp theo |
| TC154 | Event loop | late callback sau Skip/Cancel bị generation guard loại |
| TC155 | Event loop | INFO/DEMO Back rebuild previous step |
| TC156 | Event loop | ACTION Back disabled mặc định |
| TC157 | Event loop | Esc trên MainWindow cancel Tour + full cleanup |
| TC158 | Modal E2E | action mở `QDialog.exec()` và step tiếp resolve widget dialog |
| TC159 | Modal | `finished(Rejected)` đánh DialogHandle inactive ngay |
| TC160 | Modal | `accepted()` lifecycle xử lý an toàn |
| TC161 | Modal | modal Esc thuộc QDialog, Tour không intercept |
| TC162 | UI component | Spotlight chuyển host MainWindow ↔ QDialog |
| TC163 | UI component | hole cutout để mouse rơi tự nhiên xuống target |
| TC164 | UI component | dim region ngoài target ngăn interaction ngoài tour |
| TC165 | UI component | resize/move/layout cập nhật spotlight geometry |
| TC166 | Persistence | progress round-trip schema v1 |
| TC167 | Persistence | atomic write giữ canonical cũ nếu replace fail |
| TC168 | Persistence | corrupt JSON quarantine và trả empty progress |
| TC169 | Persistence | quarantine fail → read-only, không overwrite corrupt file |
| TC170 | Persistence | future `schema_version` không downgrade/overwrite |
| TC171 | Persistence | old schema migrate in-memory; rewrite chỉ khi mutation |
| TC172 | Persistence | content version cũ → OUTDATED |
| TC173 | Persistence | stored newer content version không bị downgrade |
| TC174 | UX | Completed/Dismissed/Outdated render đúng CTA |
| TC175 | UX | prerequisite fail không mutate Project/app state |
| TC176 | UX | Help Search debounce trong 150–200 ms |
| TC177 | UX | Shortcut page đọc runtime shortcut, không duplicate key |
| TC178 | First-run | clean launch → banner offer, không auto-start Tour |
| TC179 | First-run | external-open suppress banner nhưng không DISMISSED |
| TC180 | First-run | Recovery startup suppress banner nhưng không DISMISSED |
| TC181 | First-run | “Để sau”/explicit dismiss → DISMISSED |
| TC182 | First-run | Start → DISMISSED trước Tour; complete → COMPLETED |
| TC183 | First-run | bắt đầu workflow khác → banner hide, progress unchanged |
| TC184 | Demo | valid GIF load/play/stop/release |
| TC185 | Demo | missing/corrupt GIF → text fallback, Tour tiếp tục |
| TC186 | Packaging | PyInstaller spec bundle `resources/help` + `resources/tutorials` |
| TC187 | Packaging | packaged app resolve resource bằng `RuntimePaths` |
| TC188 | Packaging | packaged GIF thật chạy được qua `QMovie` |
| TC189 | Packaging | animated WebP chỉ enabled nếu characterization pass |
| TC190 | E2E | Help Center → Guide → destination → complete → progress update |
| TC191 | E2E | Import URL Hybrid Tour mở dialog thật nhưng DEMO không download/network |
| TC192 | E2E | Tour cancel/recovery không dirty Project/Revision/Recovery |
| TC193 | E2E | Help/Tour subsystem failure không làm MainWindow crash |

Tổng: **62 acceptance cases**.

---

# 13. Suggested test organization

```text
tests/
├─ test_tour_catalog.py
├─ test_tour_engine.py
├─ test_tour_anchor_registry.py
├─ test_tour_navigation.py
├─ test_tour_interaction_observer.py
├─ test_tour_spotlight.py
├─ test_tour_dialog_lifecycle.py
├─ test_tour_progress_store.py
├─ test_help_center.py
├─ test_first_run_policy.py
├─ test_demo_media_viewer.py
├─ test_help_tour_end_to_end.py
└─ test_help_tour_packaging.py
```

Test files không cần map 1:1 với TC; mọi TC phải có traceable ID trong test name/docstring/report.

---

# 14. Forbidden dependency / regression checks

Final implementation phải chứng minh:

```text
core/tutorial/tour_engine.py
→ không import PySide6.QtWidgets
→ không import PySide6.QtGui
→ không import ProjectService / MediaImportService / Whisper / Worker

resources/tutorials/*.json
→ không callback
→ không execute
→ không raw Qt signal
→ không page_index/tab_index

Help/Tour
→ không direct Project mutation
→ không RevisionTracker/Recovery mutation
```

Verification baseline:

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
git diff --check
```

Windows release gate riêng:

```text
Build PyInstaller
→ launch packaged app
→ open Help Center
→ catalog loads
→ run lightweight INFO/DEMO Tour
→ GIF plays
→ cancel/complete
→ restart
→ progress readable
```

Không cần chạy Whisper hoặc tải URL thật trong packaging smoke.

---

# 15. MainWindow integration guardrail

`ui/Gui.py` không được thêm state logic dạng:

```text
self.tutorial_step
self.is_tutorial_waiting_for_...
if tutorial_type == ...
if current_tutorial_step == ...
```

Integration budget chỉ gồm:

```text
create/wire Tour subsystem
TourBootstrap.register_main_window_anchors(...)
add HelpCenterPage
wire Help action/F1
wire runtime shortcut provider
```

Anchor registration số lượng lớn phải được tách vào bootstrap/registration functions, không nhồi toàn bộ vào MainWindow constructor.

---

# 16. Traceability theo nhóm yêu cầu

| Requirement group | Invariants | Acceptance |
|---|---|---|
| Declarative schema + confinement | INV-06, INV-22, INV-30, INV-36 | TC132–TC138 |
| Anchor/memory safety | INV-10, INV-14, INV-15 | TC139–TC142, TC151, TC159 |
| Navigation/state machine | INV-01–INV-08, INV-12, INV-32 | TC143–TC157 |
| Modal lifecycle | INV-09, INV-17, INV-18 | TC158–TC162 |
| Spotlight/input behavior | INV-13, INV-17 | TC148–TC150, TC162–TC165 |
| Progress persistence | INV-19, INV-20, INV-33–INV-35 | TC166–TC173 |
| Help/first-run UX | INV-21, INV-24–INV-27 | TC174–TC183 |
| Demo/packaging | INV-22, INV-28–INV-29, INV-36–INV-39 | TC184–TC189 |
| Full-system isolation | INV-06, INV-19, INV-21, INV-23, INV-40 | TC190–TC193 |

---

# 17. Design closure

Thiết kế đã khóa đầy đủ 5 lớp:

```text
Section 1 — Data Contract / JSON DSL
Section 2 — TourEngine State Machine / Qt event-loop orchestration
Section 3 — Ports / component boundaries / memory safety
Section 4 — Help Center UX / First Run / Demo media
Section 5 — Fault tolerance / persistence / packaging / TC132–TC193
```

Không còn quyết định kiến trúc bắt buộc nào phải để mở trước Implementation Plan.

Bước tiếp theo sau khi file spec này được review và phê duyệt là lập **Implementation Plan theo TDD: RED → GREEN → REFACTOR**, chia task theo boundary và acceptance gate. Không bắt đầu implementation code trước khi spec file được nghiệm thu.
