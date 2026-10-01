# C4 — Demo Capture Pipeline — Design Specification

**Trạng thái:** ✅ KIẾN TRÚC ĐÃ PHÊ DUYỆT — CHỜ REVIEW FILE CUỐI  
**Ngày:** 2026-09-08  
**Nhánh:** `codex/help-center-guided-tour`  
**Nền:** C3 Demo Media Viewer đã đóng tại `8cff9bfcaf4ca469310b662f3a4d7905acba2668`

---

# 1. Mục tiêu

Thiết kế phân hệ **C4 — Demo Capture Pipeline** cho AI Subtitle Studio để tự động tạo PNG/GIF minh họa thao tác UI và lưu vào:

```text
resources/tutorials/assets/
```

Các asset sau đó chỉ được **Guided Tour runtime consume** qua pipeline C3 đã hoàn thiện.

Nguyên tắc kiến trúc trung tâm:

> **Generation ≠ Consumption**

C4 là developer tooling độc lập. C4 không được làm thay đổi lifecycle, state machine hoặc behavior của Guided Tour đã đóng ở C3.

Luồng tổng quát:

```text
Developer Scenario
        ↓
Demo Capture Pipeline
        ↓
PNG/GIF local asset
        ↓
resources/tutorials/assets/
        ↓
TourCatalog / DemoSpec
        ↓
DemoMediaViewer
```

C4 phải đạt các mục tiêu sau:

- deterministic ở Mode A;
- headless-friendly ở Mode A;
- semantic-target based, không hardcode screen coordinates;
- không chiếm chuột/bàn phím OS trong Mode A;
- hỗ trợ capture vùng target hoặc toàn cửa sổ;
- tạo PNG/GIF theo batch;
- bảo vệ asset hiện có bằng validation + atomic replace;
- CI chỉ validate committed assets, không regenerate;
- Mode B dùng real production UI/services nhưng vẫn nằm trong sandbox do capture tool sở hữu.

---

# 2. Ngoài phạm vi

C4 **không** bao gồm:

- sửa `TourEngine`;
- sửa Guided Tour runtime behavior;
- sửa `DemoMediaViewer` lifecycle;
- sửa Spotlight behavior;
- attach vào AI Subtitle Studio instance mà người dùng đang chạy;
- hardcoded `x/y/width/height` registry;
- OS-level automation trong Mode A;
- tự regenerate GIF trong CI;
- MP4 consumption;
- network media;
- arbitrary Python callback/lambda trong scenario;
- JSON/YAML scenario DSL ở C4 v1;
- macro recorder/replay;
- pixel-diff based UI settling;
- per-scenario override cho asset safety limits;
- multi-file filesystem transaction guarantee;
- runtime dependency bắt buộc chỉ để phục vụ developer capture tooling.

C3 chỉ được mở lại nếu C4 tạo regression trực tiếp vào behavior đã đóng.

---

# 3. Kiến trúc nền tảng đã khóa

## 3.1. Generation / Consumption boundary

```text
Generation side                         Consumption side
────────────────                       ────────────────
DemoScenarioRegistry                    TourCatalog
        ↓                                   ↓
DemoCaptureRunner                       DemoSpec
        ↓                                   ↓
CaptureEnvironment                      TourEngine
        ↓                                   ↓
CaptureTargetResolver                   DemoMediaViewer
        ↓
UIActionDriver
        ↓
FrameCaptureService
        ↓
FrameNormalizer
        ↓
PNG/GifEncoder
        ↓
TutorialAssetValidator
        ↓
ArtifactWriter
        ↓
resources/tutorials/assets/
```

C4 không được phụ thuộc vào:

```text
TourEngine
SpotlightLayer
Tour progress
DemoMediaViewer lifecycle
TourCatalog orchestration
```

C4 có thể tái sử dụng các **semantic UI anchor** hiện có thông qua adapter nhưng không tái sử dụng Guided Tour state machine.

## 3.2. Execution strategy

Hai execution mode:

```text
Mode A — ISOLATED     ← DEFAULT
Mode B — REAL_APP     ← FALLBACK, single-scenario only
```

Mode là thuộc tính của **Runner/environment**, không phải thuộc tính của `CaptureScenario`.

---

# 4. Package boundary đề xuất

```text
core/demo_capture/
├─ models.py
├─ registry.py
├─ ports.py
├─ runner.py
├─ validation.py
├─ errors.py
└─ batch.py

ui/demo_capture/
├─ anchor_registry_adapter.py
├─ action_driver.py
├─ navigation_adapter.py
├─ frame_capture.py
├─ frame_normalizer.py
├─ isolated_app_factory.py
├─ real_app_capture_factory.py
└─ real_app_session.py

tools/demo_capture/
├─ __init__.py
├─ __main__.py
└─ cli.py

resources/tutorials/assets/
```

Tên file cụ thể có thể được tinh chỉnh trong implementation plan nếu trách nhiệm không thay đổi. Boundary phải giữ nguyên: core không phụ thuộc trực tiếp vào QWidget implementation; UI adapters hiện thực các port cần Qt.

---

# 5. Scenario model

C4 v1 dùng **Python immutable DTO**, không dùng JSON/YAML parser.

Lý do:

- đây là developer tooling;
- type-safe;
- IDE autocomplete/refactor tốt;
- không cần schema parser riêng;
- không phát sinh runtime parsing ambiguity;
- phù hợp pattern `@dataclass(frozen=True)` đã dùng ở Guided Tour models.

## 5.1. CaptureScenario

Aggregate root:

```text
CaptureScenario
├─ id: str
├─ target: CaptureTarget
├─ profile: CaptureProfile
├─ actions: tuple[CaptureAction, ...]
└─ output: OutputSpec
```

Scenario chỉ mô tả:

```text
UI nào cần chuẩn bị
→ thao tác gì
→ capture vùng nào
→ ghi asset gì
```

Scenario không được chứa:

```text
Tour ID
Tour step ID
DemoSpec
Spotlight
Tour progress
callback/lambda
raw QWidget instance
screen coordinates
```

## 5.2. CaptureTarget

`CaptureTarget` chỉ mô tả **WHERE**:

```text
CaptureTarget
├─ scope
├─ semantic_id
└─ padding
```

Enum scope:

```text
TARGET_REGION   ← default
FULL_WINDOW
```

Rules:

```text
TARGET_REGION
→ semantic_id required
→ padding >= 0

FULL_WINDOW
→ semantic_id = None
→ padding ignored
```

Defaults:

```text
scope   = TARGET_REGION
padding = 16 px
```

Không đặt vào `CaptureTarget`:

```text
fps
window_size
DPI config
output scale
wait timeout
```

## 5.3. CaptureProfile

`CaptureProfile` mô tả **HOW**:

```text
CaptureProfile
├─ window_size = (800, 600)
├─ fps = 10
├─ output_scale = 1.0
└─ default_wait_timeout_ms = 3000
```

Validation:

```text
width > 0
height > 0
1 <= fps <= 30
output_scale > 0
default_wait_timeout_ms > 0
```

Boundary:

```text
CaptureTarget  = WHERE
CaptureProfile = HOW
```

## 5.4. OutputSpec

```text
OutputSpec
├─ filename
└─ format
```

Format v1:

```text
PNG
GIF
```

Rules:

- `filename` phải là basename thuần, không chứa directory traversal;
- absolute path bị từ chối;
- extension phải khớp format;
- output root không được scenario hoặc CLI override;
- `ArtifactWriter` sở hữu `resources/tutorials/assets/`.

PNG ghi final normalized frame.

GIF ghi full normalized frame sequence.

Các policy như file-size limit, max duration, atomic replace hoặc encoder optimization không nằm trong `OutputSpec`.

---

# 6. DemoScenarioRegistry

`DemoScenarioRegistry` chỉ có ba trách nhiệm:

```text
store
validate
lookup
```

API concept:

```text
get(scenario_id)
all()
ids()
```

Registry startup validation phải phát hiện:

- duplicate scenario ID;
- duplicate output filename;
- invalid `CaptureTarget`;
- invalid `CaptureProfile`;
- invalid `OutputSpec`;
- invalid action DTO;
- format/extension mismatch.

Registry **không resolve QWidget khi register**. Dynamic widget/modal/drawer có thể chưa tồn tại hoặc chưa visible ở thời điểm registry construction.

Registry không được biết:

```text
TourCatalog
DemoSpec
TourDefinition
TourEngine
```

---

# 7. Action DSL

Scenario phải declarative; Runner/Driver mới imperative.

Nguyên tắc:

> **Scenario declarative — Runner imperative**

C4 v1 dùng typed action hierarchy thay vì một DTO chứa nhiều optional field.

```text
CaptureAction
├─ ClickAction
├─ SetTextAction
├─ SelectAction
├─ NavigateAction
├─ WaitVisibleAction
├─ WaitHiddenAction
├─ WaitSettledAction
└─ HoldAction
```

Không action nào được chứa arbitrary executable callback.

## 7.1. CLICK

Concept:

```text
CLICK(target="workspace.generate_button")
```

Flow:

```text
semantic target
↓
CaptureTargetResolver
↓
AnchorRegistryCaptureAdapter
↓
AnchorRegistry.resolve()
↓
AnchorHandle
↓
AnchorRegistry.get_widget()
↓
UIActionDriver.click(widget)
```

**CLICK không implicit WAIT_VISIBLE.**

Nếu target chưa sẵn sàng:

```text
CLICK
→ FAIL
```

Scenario phải viết rõ:

```text
WAIT_VISIBLE target
CLICK target
```

Mode A không dùng OS cursor hoặc absolute screen coordinates.

## 7.2. SET_TEXT

Concept:

```text
SET_TEXT(
    target="project.name",
    text="Demo Project"
)
```

Semantics:

```text
replace current text
```

Không append mặc định. Không sinh text ngẫu nhiên. Không nhận callable.

## 7.3. SELECT

Concept:

```text
SELECT(
    target="language.combo",
    option="Vietnamese"
)
```

Ưu tiên stable semantic value/text thay vì numeric index. Numeric index không phải contract chính vì dễ vỡ khi UI reorder options.

## 7.4. NAVIGATE

Concept:

```text
NAVIGATE(destination="workspace")
```

Flow:

```text
UIActionDriver
        ↓
CaptureNavigationAdapter
        ↓
production UI navigation mechanism
```

`NAVIGATE` chỉ trigger transition, không implicit wait hoặc sleep.

Scenario phải biểu diễn readiness rõ ràng:

```text
NAVIGATE workspace
WAIT_VISIBLE workspace.generate_button
WAIT_SETTLED
```

`CaptureNavigationAdapter` độc lập với:

```text
TourEngine
TourCatalog
SurfacePreparer orchestration
```

## 7.5. WAIT_VISIBLE

```text
WAIT_VISIBLE(target, timeout=None)
```

`timeout=None` dùng `CaptureProfile.default_wait_timeout_ms`.

Semantics theo anchor resolution:

| Resolution | Behavior |
|---|---|
| `RESOLVED` | SUCCESS |
| `NOT_VISIBLE` | tiếp tục chờ |
| `NOT_FOUND` | tiếp tục chờ |
| `INVALID` | FAIL |
| resolver exception/reason | FAIL |
| timeout | `WAIT_TIMEOUT` |

`NOT_FOUND` không fail ngay vì dynamic widget có thể chưa được tạo.

## 7.6. WAIT_HIDDEN

```text
WAIT_HIDDEN(target, timeout=None)
```

Semantics:

| Resolution | Behavior |
|---|---|
| `RESOLVED` | tiếp tục chờ |
| `NOT_VISIBLE` | SUCCESS |
| `NOT_FOUND` | SUCCESS |
| `INVALID` | FAIL |
| resolver exception | FAIL |

`NOT_FOUND` được coi là hidden vì widget có thể đã bị destroy/unregister hoàn toàn.

`INVALID` không được coi là hidden để tránh che lỗi widget/resolver.

## 7.7. WAIT_SETTLED

`WAIT_SETTLED` có semantics hẹp:

```text
Qt UI/layout đạt structural stability
```

Không có nghĩa là:

```text
background job finished
data loaded
model inference finished
pixel image stopped changing
```

Runner phải pump Qt event loop và quan sát structural state của capture root. Success khi geometry/visibility/layout state không đổi qua số observation cycle liên tiếp do implementation định nghĩa thống nhất.

Không dùng pixel-diff vì dễ bị phá bởi cursor blink, video, progress indicator hoặc animation.

Không expose `quiet_ms` per scenario trong C4 v1 để tránh magic timing numbers.

## 7.8. HOLD

```text
HOLD(duration_ms)
```

Validation:

```text
duration_ms > 0
```

Semantics:

```text
giữ UI ở trạng thái hiện tại
+
pump Qt event loop
+
tiếp tục capture frame cadence
```

Không block GUI thread bằng `time.sleep()`.

`HOLD` cho scenario author quyết định trạng thái cuối/giữa cần được người xem nhìn trong bao lâu.

---

# 8. Semantic Target Resolution

Repo đã có `ui/tutorial/anchor_registry.py`. C4 tái sử dụng semantic anchors qua adapter, không tạo registry coordinates thứ hai.

Boundary:

```text
CaptureTargetResolver (Protocol)
        ↑
AnchorRegistryCaptureAdapter
        ↓
AnchorRegistry
```

Flow:

```text
semantic_id
→ resolve_widget()
→ AnchorRegistry.resolve()
→ AnchorHandle
→ AnchorRegistry.get_widget()
→ QWidget
```

C4 giữ nguyên semantics hiện hữu của `AnchorStatus`:

```text
RESOLVED
NOT_FOUND
INVALID
NOT_VISIBLE
```

Resolver error phải được chuyển thành structured C4 failure, không được silently fallback sang screen coordinate.

---

# 9. Capture Environment

## 9.1. Mode A — ISOLATED

Mode A là mặc định.

```text
MainWindow test riêng
+ temp profile
+ mock/in-memory dependencies
+ fixed viewport
+ semantic UI actions
+ QWidget.grab()
```

Mục tiêu:

```text
deterministic
headless-friendly
không chiếm OS mouse/keyboard
batch-stable
```

Lifecycle:

```text
construct MainWindow
→ resize(800,600)
→ show()
→ processEvents()
→ WAIT_SETTLED
→ run scenario
→ cleanup
```

Headless có thể vẫn `show()` qua Qt offscreen/Xvfb.

Pattern isolated MainWindow hiện có trong test suite được tái sử dụng về mặt lifecycle: `QApplication`, temporary runtime path, mocked services, `show()`, `processEvents()`, cleanup.

## 9.2. DPI policy

Determinism không phụ thuộc việc Windows thật đang ở 100/125/150%.

Guarantee chính:

```text
fixed logical viewport
→ QWidget.grab()
→ QPixmap/QImage
→ frame normalization
→ output asset
```

Có thể dùng environment như:

```text
QT_SCALE_FACTOR=1
QT_QPA_PLATFORM=offscreen
```

nhưng đó không phải correctness guarantee chính.

---

# 10. Frame Capture

## 10.1. Capture scopes

```text
TARGET_REGION   ← default
FULL_WINDOW
```

`TARGET_REGION`:

```text
semantic target
→ resolve QWidget
→ map geometry tới capture root
→ expand padding
→ clip theo root/window bounds
→ grab
```

Geometry được resolve động theo từng frame; không lưu hardcoded rectangle.

`FULL_WINDOW` dùng cho macro-context như:

- Dashboard → Workspace;
- navigation toàn app;
- modal toàn màn hình;
- Help Center → Guide.

## 10.2. Frame cadence

Runner sở hữu monotonic frame clock.

Default:

```text
fps = 10
```

Cadence nominal:

```text
100 ms/frame
```

GIF flow:

```text
prepare environment
↓
resolve capture root
↓
capture initial frame
↓
execute actions
↓
pump Qt events
↓
capture transition states
↓
WAIT/HOLD vẫn cooperative với frame clock
↓
capture final frame
↓
normalize
↓
encode
```

`WAIT_*` và `HOLD` không được block frame scheduler.

---

# 11. FrameNormalizer

TARGET_REGION có thể đổi kích thước trong quá trình animation. GIF yêu cầu canonical frame dimensions.

C4 không stretch từng frame về size frame đầu hoặc frame cuối.

Rule:

```text
raw frames
↓
find max width / max height của sequence
↓
create canonical canvas
↓
center-pad frame nhỏ hơn
↓
apply output_scale
↓
encode
```

Guarantee:

```text
❌ stretch frame
✅ pad canvas
```

Mục tiêu là giữ geometry tự nhiên khi drawer/modal/widget mở rộng hoặc co lại.

---

# 12. Encoder boundary

Encoder là implementation detail phía generation.

Contract:

```text
PNG encoder
→ một normalized frame
→ valid PNG

GifEncoder
→ normalized frame sequence
→ animated GIF
→ frame timing theo CaptureProfile.fps
```

C4 architecture **không khóa một thư viện encoder cụ thể**. Concrete encoder được chọn trong implementation plan dựa trên capability, testability và dependency boundary, với các constraint bắt buộc:

- không làm Guided Tour consumption phụ thuộc encoder;
- không thêm runtime dependency không cần thiết cho production app;
- output phải decode được bởi validator;
- GIF phải tuân theo validation limits;
- encoder failure không được chạm final asset.

Việc không khóa library là chủ ý: behavioral contract là kiến trúc; concrete package là implementation detail.

---

# 13. Artifact validation

`TutorialAssetValidator` là gatekeeper độc lập.

Nó được dùng ở hai flow:

```text
Generation
Capture → Encode → Validator → ArtifactWriter
```

và:

```text
CI
Registry + committed assets → Validator → PASS/FAIL
```

CI validation không cần:

```text
QWidget
MainWindow
DemoCaptureRunner
TourEngine
```

## 13.1. Validation policy v1

| Rule | PNG | GIF |
|---|---:|---:|
| Max width | 1600 px | 1600 px |
| Max height | 1200 px | 1200 px |
| Max pixels/frame | 1,920,000 | 1,920,000 |
| Max filesize | 2 MiB | 8 MiB |
| Frame count | 1 | 2–200 |
| Max duration | — | 20 s |
| Decode required | yes | yes |
| Correct magic/format | yes | yes |

Policy là global system policy; scenario không override.

## 13.2. Validation pipeline

```text
path confinement
↓
exists
↓
regular file
↓
extension ↔ OutputSpec
↓
magic/decoder format
↓
decodable
↓
dimensions
↓
frame count
↓
duration
↓
file size
↓
scenario/output uniqueness
```

Nếu decoder cung cấp per-frame dimensions, validator phải verify canonical frame-size invariant cho GIF sau normalization.

Một file đúng extension nhưng sai magic hoặc decode lỗi là FAIL.

---

# 14. ArtifactWriter và atomic output

Scenario đơn:

```text
existing final asset
        │
        │ untouched
        ↓
generate temp asset
        ↓
validate
        ↓ PASS
atomic replace
        ↓
final asset
```

Nếu bất kỳ bước nào fail:

```text
existing final asset giữ nguyên
temp asset cleanup
scenario FAIL
```

Không chấp nhận:

```text
0-byte final asset
half-written final asset
xóa old asset trước khi new asset validate
```

---

# 15. Failure model

Scenario fail-fast tại action đầu tiên vi phạm contract.

Không:

- silently skip;
- auto-recover bằng action khác;
- implicit wait;
- fallback sang coordinates.

Structured diagnostic phải chứa tối thiểu:

```text
scenario_id
action_index
action_kind
semantic_target nếu có
error_code
message
```

Error categories v1:

```text
INVALID_SCENARIO
TARGET_NOT_FOUND
TARGET_NOT_VISIBLE
TARGET_INVALID
TARGET_RESOLUTION_ERROR
WAIT_TIMEOUT
NAVIGATION_FAILED
ACTION_FAILED
CAPTURE_FAILED
ENCODE_FAILED
OUTPUT_VALIDATION_FAILED
WRITE_FAILED
REAL_APP_ENVIRONMENT_UNAVAILABLE
REAL_APP_OWNERSHIP_FAILED
DESKTOP_INTERACTION_FAILED
CLEANUP_FAILED
```

Không cần một exception class riêng cho từng code; một structured code + context contract là đủ.

---

# 16. Developer CLI

C4 có entrypoint riêng:

```text
python -m tools.demo_capture
```

Tuyệt đối không thêm C4 flags vào `main.py`.

Lý do: production `main.py` sở hữu normal startup, single-instance, recovery, IPC và user application lifetime. Developer capture tooling không được đi qua lifecycle đó.

## 16.1. Commands

```text
python -m tools.demo_capture list

python -m tools.demo_capture generate open_generate_drawer

python -m tools.demo_capture generate open_generate_drawer --mode isolated

python -m tools.demo_capture generate open_generate_drawer --mode real

python -m tools.demo_capture generate --all

python -m tools.demo_capture validate
```

Commands:

```text
list
generate
validate
```

### `list`

Chỉ đọc registry. Không cần QApplication/MainWindow và không generate asset.

### `generate`

Mutually exclusive:

```text
generate <scenario-id>
```

hoặc:

```text
generate --all
```

`generate foo --all` bị từ chối.

Mode:

```text
--mode isolated   ← default
--mode real
```

CLI không expose arbitrary output directory ở C4 v1.

### `validate`

Chỉ validate registry/output mapping và committed assets theo global policy. Không regenerate.

## 16.2. Exit codes

| Code | Meaning |
|---:|---|
| `0` | SUCCESS |
| `1` | generation/runtime failure |
| `2` | invalid CLI hoặc invalid registry |
| `3` | committed-asset validation failure |
| `4` | requested execution environment unavailable |

Exit code phục vụ shell/CI; chi tiết lỗi nằm trong structured diagnostic.

---

# 17. Source-checkout-only generation

C4 generator chỉ chạy từ source checkout.

```text
Generation
→ source checkout only

Consumption
→ dev resources hoặc packaged resources
```

Nếu app đang ở frozen/PyInstaller context:

```text
sys.frozen == True
```

thì `generate` phải fail với environment-unavailable semantics.

Không cố ghi vào:

```text
_internal/resources
_MEIPASS
installed application directory
```

`RuntimePaths` vẫn là source of truth cho resource path convention, nhưng generation không biến packaged resources thành writable state.

---

# 18. Batch generation

`generate --all` chỉ hỗ trợ `ISOLATED`.

Reject:

```text
generate --all --mode real
```

## 18.1. Fresh environment per scenario

Mỗi scenario trong batch chạy trong environment sạch riêng để ngăn state leakage giữa scenario.

```text
Scenario A
→ create isolated environment
→ run
→ cleanup

Scenario B
→ create isolated environment mới
→ run
→ cleanup
```

Không reuse mutable MainWindow state giữa toàn batch.

## 18.2. Staging

Không overwrite final asset ngay sau từng scenario.

```text
Registry validation
        ↓
create batch staging dir
        ↓
A → staging/A.gif → validate
B → staging/B.gif → validate
C → staging/C.png → validate
        ↓
ALL PASS?
  │
  ├─ NO → discard staging
  │       final assets untouched
  │
  └─ YES
        ↓
      commit assets
        ↓
      per-file atomic replace
```

Scenario level:

```text
fail-fast tại action đầu tiên lỗi
```

Batch level:

```text
scenario độc lập tiếp tục chạy
→ collect full failure report
```

Nếu bất kỳ scenario fail:

```text
Batch FAILED
Final assets changed: NO
```

## 18.3. Atomicity guarantee

C4 không tuyên bố multi-file filesystem transaction.

Guarantee chính xác:

```text
✅ không commit final asset trước khi toàn batch generate + validate PASS
✅ mỗi final file atomic replace riêng
❌ process/filesystem crash giữa commit phase có thể tạo mixed batch
```

Đây là giới hạn được chấp nhận ở C4 v1.

---

# 19. Mode B — REAL_APP boundary

Mode B không có nghĩa là attach vào process thật của user.

Định nghĩa:

> **Capture-owned Real App Session**

Mode B dùng production-quality UI/services nhưng toàn bộ session do capture tool sở hữu.

```text
DemoCaptureRunner
        ↓
RealAppCaptureEnvironment
        ↓
RealAppCaptureFactory
        ↓
production MainWindow
+ real application services/adapters
+ temporary capture profile
```

Khác Mode A:

```text
Mode A
MainWindow + mock/in-memory/test services

Mode B
MainWindow + production-quality services/adapters
```

Cả hai vẫn chạy trong capture-owned process/session.

## 19.1. No `main.main()`

Mode B tuyệt đối không gọi `main.main()`.

Không kéo vào:

```text
SingleInstanceGuard
recovery scan
IPC
normal startup argv behavior
user RuntimePaths state
normal app lifetime
```

Nếu cần reuse production construction, có thể refactor một shared composition helper trong implementation, nhưng dependency direction phải là:

```text
main.py ─┐
         ├→ shared production composition helper
Mode B ──┘
```

Không:

```text
Mode B → main.py
```

## 19.2. Temporary profile sandbox

Mode B phải redirect capture-owned writable runtime state vào temporary directory trước khi construct real services.

Không đọc/ghi user profile tại:

```text
%LOCALAPPDATA%\AI Subtitle Studio
```

Mode B không được:

- load user settings;
- mark tutorial progress của user;
- touch user recovery sessions;
- modify recent projects;
- write mutable user state vào real profile.

Production resources có thể được đọc; mutable runtime state phải ở sandbox.

## 19.3. No attach-existing

C4 v1 không hỗ trợ:

```text
ATTACH_EXISTING
--attach-existing
```

Lý do:

- unknown user state;
- unsaved work;
- active generation;
- recovery state;
- modal đang mở;
- project hiện tại;
- selected subtitle;
- plugin/service state.

Không có restore transaction đáng tin cậy để hoàn nguyên toàn bộ state này.

## 19.4. Mode B lifecycle

```text
ENTER
────────────────────
save process environment sẽ override
create temp profile
create real capture environment
create capture-owned MainWindow
resize/show/settle
establish ownership

RUN
────────────────────
execute exactly one scenario
capture frames
encode staging artifact
validate

EXIT — always in finally
────────────────────
stop capture clock
close owned dialogs/windows
close owned MainWindow
deleteLater()
processEvents()
shutdown owned services
cleanup temp profile
restore overridden environment
restore desktop control best-effort
```

Cleanup failure làm toàn run FAIL và không cho commit artifact.

## 19.5. QWidget ownership

Không cleanup bằng:

```text
for every QApplication.topLevelWidget:
    close()
```

Session chỉ cleanup object do `RealAppCaptureSession` sở hữu.

Ownership phải track ít nhất:

```text
MainWindow
owned dialogs/windows
capture-owned services/resources
```

## 19.6. GUI requirement

`ISOLATED` có thể chạy offscreen/Xvfb.

`REAL_APP` yêu cầu actual GUI session khi scenario cần desktop interaction.

Mode B không phải CI requirement.

---

# 20. OS interaction boundary

Mode A:

```text
OS input forbidden
```

Mode B:

```text
semantic Qt interaction first
OS interaction fallback only
```

Nếu tương lai có action vượt Qt boundary, OS interaction phải đi qua explicit port:

```text
DesktopInteractionPort
```

Ví dụ hợp lệ trong tương lai:

```text
native file picker
external window
OS drag/drop
```

Action DSL vẫn mô tả semantic intent; Driver chọn backend.

## 20.1. DesktopInteractionLease

Nếu cần foreground/input thật:

```text
save previous desktop context
↓
activate capture-owned window
↓
perform allowed OS interaction
↓
restore focus/control best-effort
```

Nếu pointer bị di chuyển:

```text
save pointer location
→ action
→ restore pointer location best-effort
```

Windows không bảo đảm tuyệt đối foreground restoration. Vì vậy restore desktop focus là ergonomic best-effort guarantee, không phải correctness guarantee.

Correctness guarantee là:

```text
C4 không mutate user app data
C4 không attach/mutate existing user AI Subtitle Studio process
```

---

# 21. CI strategy

CI không regenerate PNG/GIF.

CI chỉ validation:

```text
scenario registry valid
scenario/output mapping valid
asset tồn tại
asset confined dưới resources/tutorials/assets/
format/magic hợp lệ
asset decode được
dimensions trong limit
file size trong limit
GIF frame count/duration trong limit
output filenames unique
```

Lý do không regenerate:

```text
font rendering differences
GPU/headless differences
binary noise
non-deterministic artifact diff
repository churn
```

CI gate không phụ thuộc DemoCaptureRunner hoặc Mode B.

---

# 22. Example scenario

Conceptual scenario:

```text
Scenario: open_generate_drawer

Target
  scope       TARGET_REGION
  semantic_id workspace.generate_panel
  padding     16

Profile
  viewport             800 × 600
  fps                  10
  output_scale         1.0
  default_wait_timeout 3000 ms

Actions
  NAVIGATE workspace
  WAIT_VISIBLE workspace.generate_button
  WAIT_SETTLED
  CLICK workspace.generate_button
  WAIT_VISIBLE workspace.generate_panel
  HOLD 800 ms

Output
  GIF
  open_generate_drawer.gif
```

Scenario không biết Qt implementation cụ thể, Guided Tour step ID hoặc DemoSpec.

---

# 23. Full system architecture

```text
                       Developer CLI
                            │
              ┌─────────────┼─────────────┐
              │             │             │
             list        generate       validate
              │             │             │
              ▼             ▼             ▼
       ScenarioRegistry   Runner    AssetValidator
                            │
                  ┌─────────┴─────────┐
                  │                   │
              ISOLATED            REAL_APP
                  │                   │
         IsolatedAppFactory   RealAppCaptureFactory
                  │                   │
                  └─────────┬─────────┘
                            ▼
                     UIActionDriver
                     ┌──────┴───────┐
                     ▼              ▼
              TargetResolver   NavigationAdapter
                     │
                AnchorRegistry
                            │
                            ▼
                   FrameCaptureService
                            │
                            ▼
                    FrameNormalizer
                            │
                            ▼
                       Encoder
                            │
                            ▼
                    staging artifact
                            │
                            ▼
                    AssetValidator
                            │
                            ▼
                    ArtifactWriter
                            │
                       atomic replace
                            │
                            ▼
             resources/tutorials/assets/
```

CI:

```text
Repository
   │
   ├─ DemoScenarioRegistry
   │
   └─ committed tutorial assets
              │
              ▼
      TutorialAssetValidator
              │
          PASS / FAIL
```

---

# 24. TDD strategy

C4 dùng:

```text
Outside-In contract
→ Bottom-Up implementation
```

Thứ tự implementation/test được định hướng như sau:

```text
1. CaptureScenario / DTO validation contract RED
2. DemoScenarioRegistry contract RED
3. semantic target resolver adapter RED
4. WAIT_VISIBLE / WAIT_HIDDEN semantics RED
5. CLICK / NAVIGATE / HOLD contract RED
6. TARGET_REGION + padding RED
7. frame normalization / pad-not-stretch RED
8. frame cadence service RED
9. PNG/GifEncoder behavioral contract RED
10. TutorialAssetValidator RED
11. ArtifactWriter atomic replace RED
12. DemoCaptureRunner integration RED
13. CLI list/generate/validate RED
14. --all staging/batch contract RED
15. Isolated MainWindow → real PNG/GIF integration
16. Mode B capture-owned real app lifecycle/cleanup tests
17. CI validation-only gate
```

Implementation plan được viết riêng sau khi design spec này được review và approved.

---

# 25. Acceptance criteria

C4 chỉ được coi là hoàn tất khi tối thiểu thỏa các điều kiện sau.

## 25.1. Architecture

- Generation và Consumption không coupling ngược.
- `main.py` không chứa C4 CLI flags hoặc capture lifecycle.
- Scenario không chứa arbitrary executable code.
- Semantic targets tái sử dụng `AnchorRegistry` qua adapter.
- Không có hardcoded pixel coordinate registry.

## 25.2. Mode A

- Default 800×600, 10 FPS, padding 16.
- `QWidget.grab()` path hoạt động sau `show()`/event processing.
- Có thể chạy trong supported headless Qt environment.
- Không dùng real OS mouse/keyboard.
- Fresh environment per scenario trong batch.

## 25.3. Capture correctness

- TARGET_REGION geometry được resolve động.
- Padding clip đúng window bounds.
- Dynamic-size frames được canonicalize bằng pad, không stretch.
- HOLD tiếp tục process events và capture cadence.
- WAIT không dùng implicit magic sleeps.

## 25.4. Assets

- PNG/GIF decode thành công.
- Limits theo Section 13 được enforce.
- Invalid/corrupt asset không được commit.
- Existing valid asset không bị phá khi generation fail.
- `--all` không commit gì nếu có ít nhất một scenario fail trước commit phase.

## 25.5. Mode B

- Single scenario only.
- Không attach existing user process.
- Không gọi `main.main()`.
- Mutable runtime state được sandbox vào temp profile.
- Chỉ cleanup owned objects.
- Cleanup failure làm run fail và không commit output.

## 25.6. CI

- CI validate committed assets.
- CI không regenerate PNG/GIF.
- CI không yêu cầu Mode B.

---

# 26. Locked defaults và policies

```text
Execution default             ISOLATED
Capture scope default         TARGET_REGION
Padding                       16 px
Viewport                      800 × 600
FPS                           10
Output scale                  1.0
Default wait timeout          3000 ms
Batch mode                    ISOLATED only
PNG max size                  2 MiB
GIF max size                  8 MiB
Max dimensions                1600 × 1200
Max pixels/frame              1,920,000
GIF frame count               2–200
GIF max duration              20 s
Generation location           source checkout only
CI generation                 forbidden
Attach existing app           forbidden
```

---

# 27. Explicit design trade-offs

## 27.1. Python DTO thay vì JSON/YAML

Đổi external authoring flexibility lấy type safety và giảm infrastructure. Phù hợp vì C4 là developer tooling.

## 27.2. Explicit waits thay vì implicit waits

Scenario dài hơn một chút nhưng deterministic và dễ debug hơn.

## 27.3. Pad thay vì stretch

Có thể tạo viền/canvas trống ở frame nhỏ nhưng giữ geometry tự nhiên, không làm méo UI animation.

## 27.4. Batch staged commit

Giảm nguy cơ repository ở trạng thái half-generated. Không tuyên bố cross-file atomic transaction ngoài khả năng filesystem.

## 27.5. Capture-owned Mode B thay vì attach existing app

Không phản ánh user mutable state 100%, nhưng đổi lại bảo vệ dữ liệu và loại bỏ state pollution. Mode B nhằm dùng real production UI/services, không nhằm capture phiên làm việc thật của user.

## 27.6. Encoder library không thuộc architecture contract

Giữ dependency choice ở implementation layer. Test behavioral contract thay vì khóa project vào package cụ thể quá sớm.

---

# 28. Scope guard trước implementation

Implementation C4 không được mở rộng sang:

```text
TourEngine modification
DemoMediaViewer modification
Spotlight modification
Guided Tour progress changes
JSON/YAML capture DSL
attach-existing mode
CI regeneration
MP4 tutorial media
network capture/upload
coordinate-based automation
macro recorder
```

Nếu implementation phát hiện một requirement buộc phải phá một boundary đã lock, phải dừng và quay lại architecture review thay vì workaround trong code.

---

# 29. Kết luận

C4 được thiết kế như một **developer-side deterministic UI capture pipeline**, độc lập với Guided Tour consumption runtime.

Ba invariants quan trọng nhất:

> **Generation ≠ Consumption.**

> **Scenario mô tả semantic intent; Runner/Driver mới thực thi.**

> **Capture tooling không được chạm mutable state của phiên AI Subtitle Studio thật của người dùng.**

Sau khi file này được review và approved, bước tiếp theo là lập **C4 implementation plan** theo Outside-In contracts + Bottom-Up implementation, rồi bắt đầu TDD. Không viết production code C4 trước approval đó.
