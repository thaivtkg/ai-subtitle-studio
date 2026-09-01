# Sprint 12 — Kế hoạch triển khai Phiên âm theo ngữ cảnh & Nhập video từ URL

> **Dành cho agent thực thi:** BẮT BUỘC dùng `superpowers:subagent-driven-development` (khuyến nghị) hoặc `superpowers:executing-plans` để triển khai từng task. Mỗi bước dùng checkbox `- [ ]` để theo dõi. Mọi thay đổi production phải tuân thủ RED → GREEN → REFACTOR.

**Mục tiêu:** Khôi phục Context/Glossary cho Whisper `initial_prompt`, đồng thời thêm URL Media Import qua yt-dlp + Direct HTTP nhưng vẫn tái sử dụng toàn bộ local media pipeline hiện có.

**Kiến trúc:** Project lưu raw `TranscriptionContext`, runtime dùng `PromptContextBuilder` biên dịch thành `SubtitleGenerationRequest.prompt_context` bất biến. URL Import đi qua `MediaImportService → Adapter → MediaProbe → atomic finalize`, sau đó MainWindow mới điều phối vào `ProjectService` hoặc `QueueManager`.

**Tech stack:** Python 3.10+, PySide6, Faster-Whisper, FFmpeg/ffprobe, `yt-dlp`, `requests`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-02-sprint-12-contextual-transcription-media-import-design.md`

## Ràng buộc toàn cục

- Không Local LLM, không translation/rewrite.
- Không Replace Source của Project hiện hữu.
- Project chỉ persist `context` + `glossary`, không persist compiled prompt.
- `DEFAULT_PROMPT_BUDGET = 180` là runtime policy.
- Glossary luôn ưu tiên trước Context.
- Resume phải giữ original compiled prompt.
- URL chỉ được canonical hóa sau local download + validate + `os.replace` thành công.
- `MediaImportService` không phụ thuộc Project/Queue/MainWindow/VideoPlayer/Whisper/Timing/ArtifactStore.
- Queue-only URL media phải vào durable `RuntimePaths.get_media_imports_dir()`.
- Chỉ public HTTP(S); phải chặn SSRF/private/local/unsafe redirect.
- Không dùng `shell=True`.
- Không cookie/credential/browser-cookie/DRM bypass.
- MainWindow chỉ orchestration.
- Mỗi task phải chạy test cụ thể trước, sau đó regression liên quan.
- Final gate:

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
```

---

# Sơ đồ task / milestone

```text
Milestone A — Context Domain & Prompt
Task 1  Project Schema v2 + TranscriptionContext
Task 2  PromptContextBuilder + TokenCounter
Task 3  Generation Request + FasterWhisper + Checkpoint Resume
Task 4  Recovery + Revision semantics cho Context/Glossary
Task 5  Context Inspector UI + Generate Panel integration

Milestone B — Media Import Core
Task 6  Media Import models/errors/runtime paths
Task 7  NetworkSafetyPolicy + URLClassifier
Task 8  DirectHTTPAdapter
Task 9  YtDlpAdapter
Task 10 MediaProbe + MediaImportService + atomic finalize
Task 11 MediaImportWorker + Dialog state machine

Milestone C — Application Integration
Task 12 New Project from URL
Task 13 Add to Queue from URL
Task 14 Full E2E TC124–TC131 + security/regression closure
Task 15 Dependencies/package/CI/final verification
```

---

# Milestone A — Context Domain & Prompt

## Task 1: Project Schema v2 + `TranscriptionContext`

**Files:**
- Tạo: `core/project/transcription_context.py`
- Sửa: `core/project/project.py`
- Sửa: `core/services/project_service.py`
- Tạo: `tests/test_transcription_context.py`

**Interface tạo ra:**

```python
@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)

    def normalized(self) -> "TranscriptionContext": ...
```

`Project` sau task:

```python
@dataclass
class Project:
    ...
    transcription_context: TranscriptionContext = field(default_factory=TranscriptionContext)
    schema_version: int = 2
```

### RED

- [ ] **Bước 1: Viết test TC107 — Project v1 load không rewrite canonical file**

Trong `tests/test_transcription_context.py`:

```python
class TestTranscriptionContextProjectSchema(unittest.TestCase):
    def test_tc107_v1_project_loads_empty_context_without_rewrite(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        video = root / "video.mp4"
        video.write_bytes(b"fake-video")

        service = ProjectService()
        source = service._generate_fingerprint(str(video))
        project_dir = root / "Legacy.ai-subtitle"
        project_dir.mkdir()
        (project_dir / "artifacts").mkdir()

        project_json = {
            "schema_version": 1,
            "project_id": "legacy",
            "name": "Legacy",
            "created_at": "2026-09-02T00:00:00",
            "updated_at": "2026-09-02T00:00:00",
            "source": source.__dict__,
        }
        path = project_dir / "project.json"
        path.write_text(json.dumps(project_json), encoding="utf-8")
        before = path.read_bytes()

        project = service.open_project(str(project_dir))

        self.assertEqual(project.transcription_context.context, "")
        self.assertEqual(project.transcription_context.glossary, [])
        self.assertEqual(path.read_bytes(), before)
```

- [ ] **Bước 2: Viết test TC108 — Project v2 round-trip normalized stable order**

```python
def test_tc108_v2_round_trip_preserves_context_and_normalized_glossary(self):
    context = TranscriptionContext(
        context="Trận chiến tại Demacia",
        glossary=[" Demacia ", "demacia", "Lux", "", "Garen"],
    )
    normalized = context.normalized()
    self.assertEqual(normalized.glossary, ["Demacia", "Lux", "Garen"])
```

Sau đó tạo Project thật, `save_project()` → `open_project()` và assert:

```python
self.assertEqual(reopened.transcription_context.context, "Trận chiến tại Demacia")
self.assertEqual(reopened.transcription_context.glossary, ["Demacia", "Lux", "Garen"])
```

- [ ] **Bước 3: Chạy RED**

```bash
python -m unittest tests.test_transcription_context -v
```

Kỳ vọng: FAIL vì chưa có `TranscriptionContext` / Project schema v2.

### GREEN

- [ ] **Bước 4: Tạo `TranscriptionContext` với normalization deterministic**

```python
from dataclasses import dataclass, field

@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)

    def normalized(self) -> "TranscriptionContext":
        seen: set[str] = set()
        result: list[str] = []
        for raw in self.glossary:
            value = str(raw).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return TranscriptionContext(self.context, result)
```

- [ ] **Bước 5: Nâng `Project` lên schema v2**

`core/project/project.py` thêm import `field` và `TranscriptionContext`, sau đó:

```python
transcription_context: TranscriptionContext = field(default_factory=TranscriptionContext)
schema_version: int = 2
```

- [ ] **Bước 6: Persist/load `transcription_context` trong `ProjectService`**

Trong `save_project()`:

```python
normalized_context = self.current_project.transcription_context.normalized()
self.current_project.transcription_context = normalized_context
proj_data["transcription_context"] = asdict(normalized_context)
```

Trong `open_project()`:

```python
ctx_data = p_data.get("transcription_context") or {}
context = TranscriptionContext(
    context=str(ctx_data.get("context", "")),
    glossary=list(ctx_data.get("glossary", [])),
).normalized()
```

Khi dựng `Project(...)` truyền `transcription_context=context` và runtime schema là `max(2, int(p_data.get("schema_version", 1)))` nhưng **không ghi file khi chỉ open**.

- [ ] **Bước 7: Chạy GREEN**

```bash
python -m unittest tests.test_transcription_context -v
```

- [ ] **Bước 8: Chạy regression Project/Recovery liên quan**

```bash
python -m unittest tests.test_recovery_end_to_end tests.test_recovery_foundation -v
```

### REFACTOR + Commit

- [ ] **Bước 9: Refactor duplicate normalization nếu có, không thêm behavior mới**
- [ ] **Bước 10: Commit**

```bash
git add core/project core/services/project_service.py tests/test_transcription_context.py
git commit -m "feat: add project transcription context"
```

**Acceptance khóa:** TC107, TC108.

---

## Task 2: `PromptContextBuilder` + Token Counter

**Files:**
- Tạo: `core/transcription/__init__.py`
- Tạo: `core/transcription/token_counter.py`
- Tạo: `core/transcription/prompt_context_builder.py`
- Tạo: `tests/test_prompt_context_builder.py`

**Interface tạo ra:**

```python
DEFAULT_PROMPT_BUDGET = 180

class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...

@dataclass(frozen=True)
class CompiledPromptContext:
    text: str
    token_count: int
    max_tokens: int
    glossary_items_used: int
    glossary_items_dropped: int
    context_truncated: bool
    truncated: bool

class PromptContextBuilder:
    def __init__(self, token_counter: TokenCounterProtocol): ...
    def build(self, transcription_context: TranscriptionContext, max_tokens: int = DEFAULT_PROMPT_BUDGET) -> CompiledPromptContext: ...
```

### RED

- [ ] **Bước 1: Viết fake token counter deterministic**

```python
class WordTokenCounter:
    def count(self, text: str) -> int:
        return len(text.split()) if text.strip() else 0
```

- [ ] **Bước 2: Viết TC109 Glossary priority**

```python
def test_tc109_context_truncates_before_accepted_glossary(self):
    builder = PromptContextBuilder(WordTokenCounter())
    result = builder.build(
        TranscriptionContext(
            context="một hai ba bốn năm sáu bảy tám chín mười",
            glossary=["Demacia", "Lux"],
        ),
        max_tokens=7,
    )
    self.assertIn("Demacia", result.text)
    self.assertIn("Lux", result.text)
    self.assertTrue(result.context_truncated)
```

- [ ] **Bước 3: Viết TC110 glossary over budget giữ first-N, không partial item**

```python
def test_tc110_glossary_over_budget_keeps_first_n_whole_terms(self):
    builder = PromptContextBuilder(WordTokenCounter())
    result = builder.build(
        TranscriptionContext(glossary=["Jarvan IV", "Demacia", "Petricite Shield"]),
        max_tokens=4,
    )
    self.assertEqual(result.glossary_items_used, 1)
    self.assertEqual(result.glossary_items_dropped, 2)
    self.assertIn("Jarvan IV", result.text)
    self.assertNotIn("Demacia", result.text)
```

- [ ] **Bước 4: Viết TC111 empty input**

```python
def test_tc111_empty_context_builds_empty_prompt(self):
    result = PromptContextBuilder(WordTokenCounter()).build(TranscriptionContext())
    self.assertEqual(result.text, "")
    self.assertEqual(result.token_count, 0)
    self.assertFalse(result.truncated)
```

- [ ] **Bước 5: Chạy RED**

```bash
python -m unittest tests.test_prompt_context_builder -v
```

### GREEN

- [ ] **Bước 6: Implement protocol + simple production counter**

`token_counter.py`:

```python
from typing import Protocol

class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...

class ApproximateTokenCounter:
    def count(self, text: str) -> int:
        return len(text.split()) if text.strip() else 0
```

Production counter ở Sprint 12 chỉ cần conservative/stable; tokenizer thật có thể DI sau.

- [ ] **Bước 7: Implement Builder glossary-first**

Builder phải kiểm tra **toàn chuỗi candidate sau khi append** bằng injected counter, không ước lượng dựa trên character length.

Pseudo-code chính xác:

```python
accepted = []
for term in normalized.glossary:
    candidate = _format_prompt(accepted + [term], "")
    if counter.count(candidate) <= max_tokens:
        accepted.append(term)
    else:
        break
```

Sau đó context được thêm bằng binary/linear boundary search theo thứ tự:

```text
full context
→ sentence prefix lớn nhất fit
→ word prefix lớn nhất fit
→ character prefix cuối cùng fit
```

- [ ] **Bước 8: Chạy GREEN**

```bash
python -m unittest tests.test_prompt_context_builder -v
```

- [ ] **Bước 9: Thêm test deterministic cùng input → cùng output**

```python
a = builder.build(context, 12)
b = builder.build(context, 12)
self.assertEqual(a, b)
```

### REFACTOR + Commit

- [ ] **Bước 10: Refactor formatting helper `_compose_prompt()`**
- [ ] **Bước 11: Commit**

```bash
git add core/transcription tests/test_prompt_context_builder.py
git commit -m "feat: build bounded whisper prompt context"
```

**Acceptance khóa:** TC109, TC110, TC111.

---

## Task 3: Generation Request + FasterWhisper + immutable Resume Prompt

**Files:**
- Sửa: `core/subtitle_generation/subtitle_generation_request.py`
- Sửa: `core/subtitle_generation/faster_whisper_service.py`
- Sửa: `core/subtitle_generation/generation_service.py`
- Sửa nếu cần: `core/subtitle_generation/generation_checkpoint_manager.py`
- Sửa: `ui/subtitle_generation_panel.py`
- Tạo: `tests/test_contextual_whisper.py`
- Bổ sung: `tests/test_subtitle_generation.py`

**Interface:**

```python
SubtitleGenerationRequest(..., prompt_context: str = "")
```

### RED

- [ ] **Bước 1: TC112 exact prompt reaches Whisper**

Tạo fake model có `transcribe()` lưu kwargs:

```python
class FakeWhisperModel:
    def __init__(self):
        self.kwargs = None
    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return [], MagicMock(language="en")
```

Assert:

```python
self.assertEqual(fake_model.kwargs["initial_prompt"], "Terminology: Demacia.")
```

- [ ] **Bước 2: TC111 empty prompt không tạo effective initial_prompt**

Assert:

```python
self.assertTrue(
    "initial_prompt" not in fake_model.kwargs
    or fake_model.kwargs["initial_prompt"] is None
)
```

- [ ] **Bước 3: TC113 Resume giữ prompt P**

Flow test với checkpoint thật:

```text
request.prompt_context = "P"
start_generation()
checkpoint.request_data["prompt_context"] == "P"
project.transcription_context đổi thành P2
resume_generation()
service.current_request.prompt_context == "P"
```

- [ ] **Bước 4: Chạy RED**

```bash
python -m unittest tests.test_contextual_whisper -v
```

### GREEN

- [ ] **Bước 5: Thêm field `prompt_context` vào request**

```python
prompt_context: str = ""
```

Đặt cuối dataclass để giữ compatibility với các call positional cũ.

- [ ] **Bước 6: Forward vào `model.transcribe()`**

Trong `FasterWhisperService.transcribe_batch()`:

```python
if request.prompt_context.strip():
    transcribe_kwargs["initial_prompt"] = request.prompt_context
```

Không sửa Timing Draft path.

- [ ] **Bước 7: Xác nhận checkpoint vốn dùng `asdict(request)` nên tự persist field mới**

Không tạo duplicate prompt field ngoài `request_data`.

- [ ] **Bước 8: Wire `PromptContextBuilder` tại lúc UI tạo request mới**

`SubtitleGenerationPanel` hoặc orchestration owner phải compile đúng một lần trước `start_generation()`:

```python
compiled = self.prompt_context_builder.build(project.transcription_context)
request = SubtitleGenerationRequest(..., prompt_context=compiled.text)
```

Không compile lại trong `SubtitleGenerationService.resume_generation()`.

- [ ] **Bước 9: Chạy GREEN + regression generation**

```bash
python -m unittest tests.test_contextual_whisper tests.test_subtitle_generation -v
```

### REFACTOR + Commit

- [ ] **Bước 10: Đảm bảo raw Context/Glossary không xuất hiện trong request/checkpoint**
- [ ] **Bước 11: Commit**

```bash
git add core/subtitle_generation ui/subtitle_generation_panel.py tests/test_contextual_whisper.py tests/test_subtitle_generation.py
git commit -m "feat: pass immutable context prompt to whisper"
```

**Acceptance khóa:** TC111, TC112, TC113.

---

## Task 4: Recovery + Revision semantics cho Context/Glossary

**Files:**
- Sửa: `core/recovery/recovery_models.py`
- Sửa: `core/recovery/recovery_validator.py`
- Sửa: `ui/Gui.py`
- Bổ sung: `tests/test_recovery_end_to_end.py`
- Bổ sung: `tests/test_transcription_context.py`

**Interface cập nhật:**

```python
@dataclass(frozen=True)
class RecoveryWorkingState:
    ...
    transcription_context: dict[str, object] = field(default_factory=dict)
```

### RED

- [ ] **Bước 1: TC114 Context logical commit → một external revision + snapshot có data**

Dùng `RevisionTracker` thật nơi có thể. Test phải assert:

```text
before_revision = N
commit một Context change
edit_revision == N + 1
is_dirty == True
snapshot.transcription_context == expected
```

- [ ] **Bước 2: TC115 crash restore Context/Glossary**

```text
unsaved context
→ capture RecoveryWorkingState
→ write_snapshot(force=True)
→ scan candidate
→ apply recovery state
→ project.transcription_context restored
→ recovered dirty baseline vẫn true
```

- [ ] **Bước 3: Validator reject malformed transcription_context**

Ví dụ:

```python
snapshot.transcription_context = {"context": 123, "glossary": "Demacia"}
```

Kỳ vọng `INVALID_TRANSCRIPTION_CONTEXT_SCHEMA`.

- [ ] **Bước 4: Chạy RED**

```bash
python -m unittest tests.test_recovery_end_to_end tests.test_transcription_context -v
```

### GREEN

- [ ] **Bước 5: Mở rộng `RecoveryWorkingState`**

```python
transcription_context: Dict[str, Any] = field(default_factory=dict)
```

Thêm cuối dataclass để giữ compatibility constructor positional cũ.

- [ ] **Bước 6: Mở rộng validator**

Rules:

```python
ctx = snapshot.transcription_context
if not isinstance(ctx, dict): fail
if not isinstance(ctx.get("context", ""), str): fail
if not isinstance(ctx.get("glossary", []), list): fail
if not all(isinstance(item, str) for item in ctx.get("glossary", [])): fail
```

- [ ] **Bước 7: Capture/apply state trong MainWindow orchestration**

Capture:

```python
"transcription_context": asdict(project.transcription_context)
```

Apply:

```python
project.transcription_context = TranscriptionContext(**state.transcription_context).normalized()
```

- [ ] **Bước 8: Context UI commit phải gọi đúng một external mutation path**

Không gọi cả `ProjectService.mark_dirty()` và nhiều signal làm double increment nếu `RevisionTracker.record_external_change()` đã là revision authority. Sau logical commit:

```python
if new_value != old_value:
    project.transcription_context = normalized
    project.state.dirty = True
    revision_tracker.record_external_change()
```

- [ ] **Bước 9: Chạy GREEN**

```bash
python -m unittest tests.test_recovery_end_to_end tests.test_revision_tracker tests.test_transcription_context -v
```

### REFACTOR + Commit

- [ ] **Bước 10: Không duplicate recovery context ở workspace/root khác**
- [ ] **Bước 11: Commit**

```bash
git add core/recovery ui/Gui.py tests/test_recovery_end_to_end.py tests/test_transcription_context.py
git commit -m "feat: recover unsaved transcription context"
```

**Acceptance khóa:** TC114, TC115.

---

## Task 5: Context Inspector UI + Generate Panel Integration

**Files:**
- Tạo: `ui/components/transcription_context_panel.py`
- Sửa: `ui/subtitle_generation_panel.py`
- Sửa: `ui/Gui.py`
- Tạo: `tests/test_transcription_context_ui.py`

**Interface UI:**

```python
class TranscriptionContextPanel(QWidget):
    context_committed = Signal(object)  # TranscriptionContext
    edit_requested = Signal()

    def set_context(self, value: TranscriptionContext) -> None: ...
    def set_prompt_diagnostics(self, compiled: CompiledPromptContext) -> None: ...
```

### RED

- [ ] **Bước 1: Test multiline Glossary one-term-per-line và debounce**

Dùng Qt test cơ bản/offscreen. Assert một chuỗi nhập nhanh chỉ emit một `context_committed` sau debounce.

- [ ] **Bước 2: Test prompt diagnostics read-only**

```text
6/6 glossary
72/180 token
Context truncated false
```

- [ ] **Bước 3: Test Generate Panel không có editor duplicate**

Chỉ có status label + `Edit Context` action.

- [ ] **Bước 4: Chạy RED**

```bash
python -m unittest tests.test_transcription_context_ui -v
```

### GREEN

- [ ] **Bước 5: Implement `TranscriptionContextPanel`**

Dùng:

```text
QPlainTextEdit context
QPlainTextEdit glossary
QTimer singleShot debounce 400 ms
QLabel diagnostics
QPushButton preview read-only (optional nếu UI hiện hữu cho phép)
```

- [ ] **Bước 6: MainWindow chỉ nối signal → domain commit**

Không đặt builder internals vào `Gui.py`.

- [ ] **Bước 7: `SubtitleGenerationPanel` hiển thị compact status**

Ví dụ:

```text
Context: Bật · 6 thuật ngữ · ~72/180 token
[Chỉnh Context]
```

Timing Draft không compile prompt.

- [ ] **Bước 8: Chạy GREEN + UI regression**

```bash
python -m unittest tests.test_transcription_context_ui tests.test_subtitle_inspector_panel tests.test_editor_ui -v
```

### REFACTOR + Commit

- [ ] **Bước 9: Giữ `Gui.py` orchestration-only**
- [ ] **Bước 10: Commit**

```bash
git add ui/components/transcription_context_panel.py ui/subtitle_generation_panel.py ui/Gui.py tests/test_transcription_context_ui.py
git commit -m "feat: add transcription context inspector"
```

**Milestone A hoàn tất khi TC107–TC115 xanh.**

---

# Milestone B — Media Import Core

## Task 6: Media Import Models, Errors và Runtime Paths

**Files:**
- Tạo: `core/media_import/__init__.py`
- Tạo: `core/media_import/media_import_models.py`
- Tạo: `core/media_import/media_import_errors.py`
- Sửa: `core/runtime/runtime_paths.py`
- Tạo: `tests/test_media_import_service.py`

**Interfaces:**

```python
class MediaImportStage(str, Enum):
    RESOLVING = "RESOLVING"
    DOWNLOADING = "DOWNLOADING"
    VALIDATING = "VALIDATING"
    FINALIZING = "FINALIZING"

@dataclass(frozen=True)
class MediaImportProgress:
    stage: MediaImportStage
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bytes_per_sec: float | None = None
    eta_seconds: float | None = None
    percent: float | None = None

@dataclass(frozen=True)
class MediaImportResult:
    local_path: str
    original_url: str
    filename: str
    size_bytes: int
    media_type: str
    metadata: dict[str, object]
```

Error:

```python
class MediaImportErrorCode(str, Enum): ...
class MediaImportError(Exception):
    code: MediaImportErrorCode
```

`RuntimePaths`:

```python
get_media_imports_dir() -> Path
```

### RED

- [ ] **Bước 1: Test RuntimePaths queue-only durable storage**

```python
self.assertEqual(
    RuntimePaths.get_media_imports_dir(),
    RuntimePaths.get_user_data_dir() / "media_imports",
)
```

- [ ] **Bước 2: Test `ensure_user_data_dirs()` tạo directory**
- [ ] **Bước 3: Test error code đầy đủ gồm `UNSAFE_URL`**
- [ ] **Bước 4: Chạy RED**

```bash
python -m unittest tests.test_media_import_service -v
```

### GREEN

- [ ] **Bước 5: Tạo immutable models/errors**
- [ ] **Bước 6: Thêm `get_media_imports_dir()` và mkdir trong RuntimePaths**
- [ ] **Bước 7: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_service -v
```

### Commit

```bash
git add core/media_import core/runtime/runtime_paths.py tests/test_media_import_service.py
git commit -m "feat: define media import contracts"
```

---

## Task 7: `NetworkSafetyPolicy` + `URLClassifier`

**Files:**
- Tạo: `core/media_import/network_safety.py`
- Tạo: `core/media_import/url_classifier.py`
- Tạo: `tests/test_media_import_adapters.py`

**Interface:**

```python
class NetworkSafetyPolicy:
    def validate_url(self, url: str) -> None: ...
    def resolve_and_validate_host(self, hostname: str) -> tuple[str, ...]: ...
    def validate_redirect(self, url: str) -> None: ...

class URLClassifier:
    def is_obvious_direct_media(self, url: str, content_type: str | None = None) -> bool: ...
```

### RED

- [ ] **Bước 1: TC131 reject scheme nguy hiểm**

Test các input:

```text
file:///etc/passwd
ftp://example.com/video.mp4
smb://server/share/video.mp4
data:text/plain,hello
javascript:alert(1)
```

Kỳ vọng `MediaImportErrorCode.UNSAFE_URL` hoặc `INVALID_URL` theo taxonomy; thống nhất trong implementation là scheme non-http(s) → `UNSAFE_URL`.

- [ ] **Bước 2: TC131 reject IP literal blocked**

```text
http://127.0.0.1/video.mp4
http://10.0.0.1/video.mp4
http://169.254.1.1/video.mp4
http://[::1]/video.mp4
```

- [ ] **Bước 3: DNS fake resolve public hostname → private IP phải reject**

Patch `socket.getaddrinfo()` để trả `192.168.1.10`.

- [ ] **Bước 4: Redirect public → private phải reject**

- [ ] **Bước 5: URLClassifier nhận `.mp4/.webm/.mov/.mkv/.m4v` là direct hint**
- [ ] **Bước 6: Chạy RED**

```bash
python -m unittest tests.test_media_import_adapters -v
```

### GREEN

- [ ] **Bước 7: Implement parsing bằng `urllib.parse.urlsplit`**
- [ ] **Bước 8: Implement IP filtering bằng `ipaddress.ip_address()`**

Reject nếu:

```python
ip.is_loopback
or ip.is_private
or ip.is_link_local
or ip.is_multicast
or ip.is_unspecified
or ip.is_reserved
```

- [ ] **Bước 9: Resolve hostname bằng `socket.getaddrinfo()` và validate mọi candidate**
- [ ] **Bước 10: `validate_redirect()` gọi lại toàn bộ URL + DNS policy**
- [ ] **Bước 11: Implement `URLClassifier` chỉ làm routing hint**
- [ ] **Bước 12: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_adapters -v
```

### REFACTOR + Commit

- [ ] **Bước 13: Tách `_validate_ip()` pure helper để test trực tiếp**
- [ ] **Bước 14: Commit**

```bash
git add core/media_import/network_safety.py core/media_import/url_classifier.py tests/test_media_import_adapters.py
git commit -m "feat: guard media urls against unsafe networks"
```

**Acceptance khóa:** phần security của TC131.

---

## Task 8: `DirectHTTPAdapter`

**Files:**
- Tạo: `core/media_import/adapters/__init__.py`
- Tạo: `core/media_import/adapters/downloader_adapter.py`
- Tạo: `core/media_import/adapters/direct_http_adapter.py`
- Bổ sung: `tests/test_media_import_adapters.py`

**Interface:**

```python
class DownloaderAdapter(Protocol):
    def download(self, request: DownloadRequest, progress_cb, is_cancelled) -> Path: ...

class DirectHTTPAdapter:
    def __init__(self, session: requests.Session, network_policy: NetworkSafetyPolicy): ...
```

### RED

- [ ] **Bước 1: TC116 stream direct media thành staged file**

Fake response:

```python
headers = {"Content-Length": "8", "Content-Type": "video/mp4"}
iter_content() -> [b"1234", b"5678"]
```

Assert file chứa đúng bytes và progress tăng.

- [ ] **Bước 2: TC120 cancel giữa stream**

Sau chunk đầu `is_cancelled()` → True, kỳ vọng `DOWNLOAD_CANCELLED` và staged file bị cleanup bởi service/adapter contract tương ứng.

- [ ] **Bước 3: TC121 network exception mapping**

`requests.Timeout` → `TIMEOUT`; `ConnectionError` → `NETWORK_ERROR`.

- [ ] **Bước 4: Redirect phải gọi `network_policy.validate_redirect()` trước khi tiếp tục**

Khuyến nghị disable automatic redirects:

```python
allow_redirects=False
```

và adapter tự loop redirect hữu hạn.

- [ ] **Bước 5: Chạy RED**

```bash
python -m unittest tests.test_media_import_adapters.TestDirectHTTPAdapter -v
```

### GREEN

- [ ] **Bước 6: Implement requests streaming với finite timeout**

Ví dụ policy:

```python
DEFAULT_TIMEOUT = (10, 30)
MAX_REDIRECTS = 5
CHUNK_SIZE = 1024 * 1024
```

- [ ] **Bước 7: TLS verification giữ mặc định `verify=True`**
- [ ] **Bước 8: Không truyền cookie/auth browser state**
- [ ] **Bước 9: Emit `MediaImportProgress(DOWNLOADING, ...)` theo chunk**
- [ ] **Bước 10: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_adapters.TestDirectHTTPAdapter -v
```

### REFACTOR + Commit

```bash
git add core/media_import/adapters tests/test_media_import_adapters.py
git commit -m "feat: stream direct http media safely"
```

**Acceptance khóa:** TC116, TC120, TC121, một phần TC131.

---

## Task 9: `YtDlpAdapter`

**Files:**
- Tạo: `core/media_import/adapters/yt_dlp_adapter.py`
- Sửa: `requirements.txt`
- Sửa: `requirements-runtime.txt`
- Bổ sung: `tests/test_media_import_adapters.py`

**Interface:**

```python
class YtDlpAdapter:
    def __init__(self, ydl_factory, network_policy: NetworkSafetyPolicy): ...
    def download(self, request: DownloadRequest, progress_cb, is_cancelled) -> Path: ...
```

### RED

- [ ] **Bước 1: TC117 supported website dùng yt-dlp adapter**

Fake `YoutubeDL` phải capture options và tạo staged output giả.

Assert options tối thiểu:

```python
self.assertTrue(opts["noplaylist"])
self.assertEqual(opts["format"], "bestvideo*+bestaudio/best")
self.assertNotIn("cookiesfrombrowser", opts)
self.assertNotIn("username", opts)
```

- [ ] **Bước 2: TC118 UnsupportedURL được classify để service fallback DirectHTTP**
- [ ] **Bước 3: TC119 auth/DRM/network không được map thành UnsupportedURL**
- [ ] **Bước 4: progress hook map bytes/speed/eta/percent**
- [ ] **Bước 5: cancellation hook abort cooperative**
- [ ] **Bước 6: Chạy RED**

```bash
python -m unittest tests.test_media_import_adapters.TestYtDlpAdapter -v
```

### GREEN

- [ ] **Bước 7: Implement bằng `yt_dlp.YoutubeDL(options)` Python API**

Không subprocess shell.

- [ ] **Bước 8: Output template chỉ trỏ vào staging app-controlled**

Ví dụ:

```python
"outtmpl": str(staging_dir / "download.%(ext)s")
```

Template do app tạo, user không chỉnh được.

- [ ] **Bước 9: Error mapping explicit**

Phân biệt ít nhất:

```text
unsupported/no extractor → UNSUPPORTED_URL
auth/private → AUTH_REQUIRED
DRM → DRM_OR_PROTECTED
network → NETWORK_ERROR/TIMEOUT
```

- [ ] **Bước 10: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_adapters.TestYtDlpAdapter -v
```

### Commit

```bash
git add core/media_import/adapters/yt_dlp_adapter.py requirements.txt requirements-runtime.txt tests/test_media_import_adapters.py
git commit -m "feat: add yt dlp media adapter"
```

**Acceptance khóa:** TC117, TC118, TC119.

---

## Task 10: `MediaProbe` + `MediaImportService` + Atomic Finalize

**Files:**
- Tạo: `core/media_import/media_probe.py`
- Tạo: `core/media_import/media_import_service.py`
- Bổ sung: `tests/test_media_import_service.py`

**Interface:**

```python
@dataclass(frozen=True)
class MediaProbeResult:
    duration_ms: int
    width: int | None
    height: int | None
    codec: str | None
    container: str | None
    fps: float | None
    extension: str

class MediaProbe:
    def probe(self, path: Path) -> MediaProbeResult: ...

class MediaImportService:
    def import_url(self, request: MediaImportRequest, progress_cb, is_cancelled) -> MediaImportResult: ...
```

### RED

- [ ] **Bước 1: TC122 ffprobe invalid/no video**

Mock `subprocess.run()` output JSON không có video stream → `NO_VIDEO_STREAM`.

- [ ] **Bước 2: MediaProbe dùng argument array + `shell=False`**

Assert call:

```python
subprocess.run([...], shell=False, ...)
```

- [ ] **Bước 3: TC123 `os.replace` failure → no canonical accepted**

Patch `os.replace` raise `OSError`, assert target không tồn tại và error `FINALIZE_FAILED`.

- [ ] **Bước 4: TC118/119 adapter routing ở service**

```text
direct hint → DirectHTTP first
web URL → yt-dlp first
UNSUPPORTED_URL → fallback allowed
AUTH/NETWORK/DRM → no fallback
```

- [ ] **Bước 5: failure/cancel cleanup staging**
- [ ] **Bước 6: Chạy RED**

```bash
python -m unittest tests.test_media_import_service -v
```

### GREEN

- [ ] **Bước 7: Implement MediaProbe ffprobe JSON parser**

Command shape:

```python
[
    ffprobe_path,
    "-v", "error",
    "-show_streams",
    "-show_format",
    "-of", "json",
    str(path),
]
```

- [ ] **Bước 8: Implement MediaImportService transaction**

```text
RESOLVING
→ choose adapter
→ DOWNLOADING
→ adapter staged output
→ VALIDATING
→ MediaProbe
→ FINALIZING
→ safe canonical path
→ os.replace
→ MediaImportResult
```

- [ ] **Bước 9: Path confinement trước finalize**

```python
resolved_target.relative_to(resolved_target_dir)
```

Nếu fail → `UNSAFE_URL` hoặc `FINALIZE_FAILED`; khuyến nghị domain riêng internal security error nhưng public taxonomy vẫn `UNSAFE_URL`.

- [ ] **Bước 10: Canonical filename do app chọn `source.<validated-ext>`**
- [ ] **Bước 11: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_service tests.test_media_import_adapters -v
```

### REFACTOR + Commit

```bash
git add core/media_import/media_probe.py core/media_import/media_import_service.py tests/test_media_import_service.py
git commit -m "feat: validate and atomically finalize imported media"
```

**Acceptance khóa:** TC118–TC123.

---

## Task 11: MediaImportWorker + Dialog State Machine

**Files:**
- Tạo: `workers/media_import_worker.py`
- Tạo: `ui/dialogs/media_import_dialog.py`
- Tạo: `tests/test_media_import_ui.py`

**Worker interface:**

```python
class MediaImportWorker(QThread):
    progress_changed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)
    cancelled = Signal()

    def cancel(self) -> None: ...
```

### RED

- [ ] **Bước 1: Worker success emit result**
- [ ] **Bước 2: Worker cancel không emit failed**
- [ ] **Bước 3: Dialog state transition IDLE → RESOLVING → ... → SUCCEEDED**
- [ ] **Bước 4: Unknown `total_bytes=None` → indeterminate progress**
- [ ] **Bước 5: Close dialog khi running gọi cancel và đợi cleanup**
- [ ] **Bước 6: Chạy RED**

```bash
python -m unittest tests.test_media_import_ui -v
```

### GREEN

- [ ] **Bước 7: Implement Worker chỉ bridge service**

Không Project/Queue mutation trong worker.

- [ ] **Bước 8: Implement Dialog**

Fields:

```text
URL
New Project / Add to Queue radio
Project name/location chỉ hiện ở New Project
progress bar
status label
Cancel
Import
```

- [ ] **Bước 9: Error code → user-friendly message**

Không dump raw exception lên UI.

- [ ] **Bước 10: Chạy GREEN**

```bash
python -m unittest tests.test_media_import_ui -v
```

### Commit

```bash
git add workers/media_import_worker.py ui/dialogs/media_import_dialog.py tests/test_media_import_ui.py
git commit -m "feat: add media import worker and dialog"
```

**Milestone B hoàn tất khi TC116–TC123 + security unit tests xanh.**

---

# Milestone C — Application Integration

## Task 12: New Project from URL → Player / Timing / Full Subtitle

**Files:**
- Sửa: `ui/Gui.py`
- Có thể sửa nhẹ: `ui/dialogs/new_project_dialog.py` chỉ nếu cần reuse path/name validation helper
- Tạo/Bổ sung: `tests/test_sprint12_end_to_end.py`

### RED

- [ ] **Bước 1: TC124 successful URL import tạo SourceInfo từ finalized local media**

Fake `MediaImportService` trả `MediaImportResult(local_path=...)`.

Assert sau orchestration:

```python
self.assertEqual(project.source.path, finalized_path)
self.assertTrue(project.source.fingerprint)
```

- [ ] **Bước 2: TC125 VideoPlayer nhận cùng finalized local path**
- [ ] **Bước 3: TC126 Timing Draft lấy `Project.source.path` hiện hữu**
- [ ] **Bước 4: TC127 Full Subtitle request lấy `Project.source.path`**
- [ ] **Bước 5: Fail/cancel trước finalize → không gọi `ProjectService.create_project()`**
- [ ] **Bước 6: Chạy RED**

```bash
python -m unittest tests.test_sprint12_end_to_end -v
```

### GREEN

- [ ] **Bước 7: Thêm action `Import Video from URL...` trong MainWindow**

MainWindow chỉ:

```text
open dialog
build MediaImportRequest
start worker
receive result
call ProjectService.create_project
_switch_recovery_session
load existing player/workspace
```

- [ ] **Bước 8: Precompute bundle path nhưng không create Project trước download**

Ví dụ:

```python
bundle = Path(root) / f"{safe_project_name}.ai-subtitle"
staging_root = bundle / "media" / ".staging" / import_id
```

- [ ] **Bước 9: Sau success mới gọi `create_project()`**
- [ ] **Bước 10: Chạy GREEN**

```bash
python -m unittest tests.test_sprint12_end_to_end -v
```

### Commit

```bash
git add ui/Gui.py tests/test_sprint12_end_to_end.py
git commit -m "feat: create projects from imported url media"
```

**Acceptance khóa:** TC124, TC125, TC126, TC127.

---

## Task 13: Add to Queue from URL + Durable App Storage

**Files:**
- Sửa: `ui/Gui.py`
- Có thể sửa: `ui/queue_widget.py` để thêm action URL
- Bổ sung: `tests/test_sprint12_end_to_end.py`

### RED

- [ ] **Bước 1: TC130 Queue-only dùng `RuntimePaths.get_media_imports_dir()`**

Assert target dạng:

```text
<user_data>/media_imports/<import-id>/source.<ext>
```

- [ ] **Bước 2: TC130 successful import gọi `QueueManager.add_video(local_path)` đúng một lần**
- [ ] **Bước 3: Assert không gọi `ProjectService.create_project()`**
- [ ] **Bước 4: Remove Queue item không xóa underlying imported file**
- [ ] **Bước 5: Chạy RED**

```bash
python -m unittest tests.test_sprint12_end_to_end.TestQueueOnlyUrlImport -v
```

### GREEN

- [ ] **Bước 6: MainWindow build queue-only target từ RuntimePaths**
- [ ] **Bước 7: Sau worker success mới `queue_manager.add_video()`**
- [ ] **Bước 8: Không tạo fake Project bundle**
- [ ] **Bước 9: Chạy GREEN**

```bash
python -m unittest tests.test_sprint12_end_to_end -v
```

### Commit

```bash
git add ui/Gui.py ui/queue_widget.py tests/test_sprint12_end_to_end.py
git commit -m "feat: add url media to durable queue storage"
```

**Acceptance khóa:** TC130.

---

## Task 14: E2E Source Guard + SSRF + Full Sprint Closure

**Files:**
- Bổ sung: `tests/test_sprint12_end_to_end.py`
- Bổ sung: `tests/test_media_import_adapters.py`
- Sửa production chỉ khi test RED chỉ ra behavior còn thiếu.

### RED

- [ ] **Bước 1: TC128 Save/close/reopen giữ source fingerprint**

Dùng real `ProjectService`, fake media file hợp lệ cho fingerprint.

- [ ] **Bước 2: TC129 Full URL E2E với injectable fake adapters/probe**

Flow test:

```text
URL
→ fake adapter staged media
→ fake/real MediaProbe valid
→ atomic finalize
→ ProjectService.create_project
→ verify Player path orchestration
→ verify Timing source path
→ verify Generation request source path
→ save
→ close
→ reopen
→ fingerprint vẫn hợp lệ
```

Không gọi Internet thật.

- [ ] **Bước 3: TC131 public hostname → redirect private phải fail `UNSAFE_URL`**
- [ ] **Bước 4: TC131 DNS re-resolution fake public→private bị reject gần connection path**
- [ ] **Bước 5: Path traversal remote title không thể thoát target dir**
- [ ] **Bước 6: Log redaction bỏ query/fragment**

Ví dụ:

```text
https://host/video?id=1&token=SECRET#fragment
→ log chỉ còn https://host/video
```

- [ ] **Bước 7: Chạy RED**

```bash
python -m unittest tests.test_sprint12_end_to_end tests.test_media_import_adapters -v
```

### GREEN

- [ ] **Bước 8: Implement đúng phần còn thiếu tối thiểu**
- [ ] **Bước 9: Chạy GREEN**

```bash
python -m unittest tests.test_sprint12_end_to_end tests.test_media_import_adapters -v
```

- [ ] **Bước 10: Chạy toàn bộ TC107–TC131 modules**

```bash
python -m unittest \
  tests.test_transcription_context \
  tests.test_prompt_context_builder \
  tests.test_contextual_whisper \
  tests.test_media_import_service \
  tests.test_media_import_adapters \
  tests.test_media_import_ui \
  tests.test_sprint12_end_to_end -v
```

### Commit

```bash
git add tests core ui workers
git commit -m "test: close Sprint 12 acceptance coverage"
```

**Acceptance khóa:** TC128, TC129, TC131 và toàn TC107–TC131.

---

## Task 15: Dependencies, Packaging, CI và Final Verification

**Files:**
- Sửa: `requirements.txt`
- Sửa: `requirements-runtime.txt`
- Sửa: `build/ai_subtitle_studio.spec`
- Sửa `.github/workflows/ci.yml` **chỉ nếu thật sự cần**
- Không sửa behavior production ngoài regression fix đã có failing test.

### RED / Verification pre-check

- [ ] **Bước 1: Xác nhận `yt-dlp` và `requests` đều declared explicit**

`requirements.txt` phải có ít nhất:

```text
yt-dlp>=<version phù hợp>
requests>=2.31.0
```

`requirements-runtime.txt` pin version reproducible.

- [ ] **Bước 2: Packaging spec phải collect/import yt-dlp nếu PyInstaller không tự discover**

Thêm khi cần:

```python
datas += collect_data_files('yt_dlp')
hiddenimports += collect_submodules('yt_dlp')
```

Không thêm nếu thử build cho thấy không cần; nhưng plan executor phải kiểm chứng bằng package test.

- [ ] **Bước 3: CI hiện dùng `pip install -r requirements.txt` và unittest discovery; chỉ sửa workflow nếu dependency/test discovery fail thực tế**

### Full Verification

- [ ] **Bước 4: Chạy full unit/integration suite**

```bash
python -m unittest discover -s tests -v
```

Kỳ vọng: 0 failure, 0 error. Skip chỉ được chấp nhận nếu có lý do môi trường đã được xác định và CI production path vẫn chạy test đó.

- [ ] **Bước 5: Compile toàn bộ**

```bash
python -m compileall core ui workers tests main.py
```

Kỳ vọng: exit 0.

- [ ] **Bước 6: Kiểm tra không có forbidden production API**

```bash
git grep -nE "load_url_video|generate_from_url|timing_from_url|shell=True|cookiesfrombrowser"
```

Kỳ vọng: không có match production trái spec; match trong test/spec/comment phải được review thủ công.

- [ ] **Bước 7: Kiểm tra `MediaImportService` không import forbidden dependencies**

```bash
git grep -nE "ProjectService|QueueManager|MainWindow|VideoPlayer|FasterWhisperService|ArtifactStore" core/media_import
```

Kỳ vọng: không có coupling forbidden.

- [ ] **Bước 8: Kiểm tra worktree sạch**

```bash
git status --short
```

- [ ] **Bước 9: Commit dependency/package changes nếu có**

```bash
git add requirements.txt requirements-runtime.txt build/ai_subtitle_studio.spec .github/workflows/ci.yml
git commit -m "build: package Sprint 12 media import dependencies"
```

- [ ] **Bước 10: Push branch và mở PR**

```bash
git push -u origin sprint-12
```

PR target:

```text
sprint-12 → master
```

---

# Mapping Acceptance Test → Task

| Acceptance | Task |
|---|---:|
| TC107 Project v1 migration | 1 |
| TC108 Project v2 normalized round-trip | 1 |
| TC109 Glossary priority | 2 |
| TC110 Glossary over budget | 2 |
| TC111 Empty prompt | 2, 3 |
| TC112 Context → Whisper | 3 |
| TC113 Immutable resume prompt | 3 |
| TC114 Revision + Recovery context edit | 4 |
| TC115 Crash restore context | 4 |
| TC116 Direct media import | 8 |
| TC117 Supported website import | 9 |
| TC118 Unsupported extractor fallback | 9, 10 |
| TC119 No masked yt-dlp failure | 9, 10 |
| TC120 Cancel cleanup | 8, 10, 11 |
| TC121 Network failure cleanup | 8, 10 |
| TC122 Invalid media | 10 |
| TC123 Atomic finalize failure | 10 |
| TC124 New Project SourceInfo | 12 |
| TC125 Player reuse | 12 |
| TC126 Timing Draft reuse | 12 |
| TC127 Full Subtitle reuse | 12 |
| TC128 Reopen source guard | 14 |
| TC129 Full URL E2E | 14 |
| TC130 Queue-only durable storage | 13 |
| TC131 SSRF/redirect guard | 7, 8, 14 |

---

# Review Gate sau mỗi Milestone

## Gate A — Contextual Transcription

Phải chứng minh:

```text
TC107–TC115 xanh
Project v1 không bị rewrite khi open
Project v2 persist normalized Context/Glossary
Prompt deterministic + bounded
Resume giữ prompt cũ
Recovery giữ unsaved Context
Timing Draft không nhận Context
```

Không qua Gate A thì không bắt đầu UI Media Import integration.

## Gate B — Media Import Core

Phải chứng minh:

```text
TC116–TC123 xanh
DirectHTTP stream không buffer whole file
YtDlpAdapter không blind fallback
MediaProbe là trust boundary
Cancel/fail cleanup staging
Atomic finalize đúng contract
Public HTTP(S) safety policy hoạt động
```

## Gate C — Application Integration

Phải chứng minh:

```text
TC124–TC131 xanh
New Project chỉ tạo sau finalize
Queue-only không fake Project
Player/Timing/Generation reuse local path
Source fingerprint survive reopen
SSRF/path/shell/log boundaries pass
```

---

# Checklist tự review Implementation Plan

## Coverage Spec

- [x] Project schema v2.
- [x] Migration v1 không rewrite.
- [x] Glossary normalization stable.
- [x] Prompt builder + token counter DI.
- [x] `initial_prompt` forwarding.
- [x] Immutable checkpoint prompt.
- [x] Recovery/Revision Context edits.
- [x] Right Inspector Context UI.
- [x] Media import models/errors/progress.
- [x] DirectHTTP adapter.
- [x] yt-dlp adapter.
- [x] MediaProbe + ffprobe.
- [x] Atomic finalize.
- [x] Durable queue-only storage.
- [x] New Project URL flow.
- [x] Queue URL flow.
- [x] SSRF/DNS/redirect guard.
- [x] Path confinement.
- [x] `shell=False`.
- [x] Log redaction.
- [x] TC107–TC131.
- [x] Packaging/dependencies/final verification.

## Placeholder scan

Không có `TBD`, `TODO`, “implement later”, hoặc task kiểu “thêm error handling” không có contract cụ thể.

## Type consistency

Tên contract dùng xuyên plan:

```text
TranscriptionContext
CompiledPromptContext
PromptContextBuilder
TokenCounterProtocol
MediaImportStage
MediaImportProgress
MediaImportResult
MediaImportErrorCode
MediaImportError
NetworkSafetyPolicy
URLClassifier
DownloaderAdapter
DirectHTTPAdapter
YtDlpAdapter
MediaProbe
MediaImportService
MediaImportWorker
```

---

# Definition of Done Sprint 12

Sprint chỉ được coi hoàn tất khi:

```text
✅ TC107–TC131 pass
✅ full unittest discovery pass
✅ compileall core/ui/workers/tests/main.py pass
✅ không regression Sprint 9–11
✅ no source replacement
✅ no URL-direct playback/transcription pipeline
✅ no forbidden MediaImportService coupling
✅ no shell=True
✅ no cookie/credential/DRM bypass surface
✅ SSRF/private/local/redirect guard pass
✅ worktree sạch
✅ GitHub CI xanh trên PR merge ref
✅ code review không còn Critical/Important
```

---

# Cách thực thi khuyến nghị

Trước khi code, tạo hoặc vào isolated worktree cho `sprint-12`, cài dependency và chạy baseline suite.

Sau đó thực hiện từng Task theo đúng vòng:

```text
RED
→ chạy test và xác nhận fail đúng lý do
→ GREEN minimal implementation
→ chạy targeted tests
→ REFACTOR
→ chạy regression liên quan
→ commit
→ review gate
→ Task kế tiếp
```

Không gom nhiều task vào một commit lớn.
