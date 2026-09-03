# Sprint 12 — Phiên âm theo ngữ cảnh & Nhập video từ URL

**Trạng thái:** ✅ ĐÃ PHÊ DUYỆT — THIẾT KẾ ĐÃ KHÓA  
**Ngày:** 2026-09-02  
**Nhánh mục tiêu:** `sprint-12`  
**Nền:** `master` sau Sprint 11 (`4f827b32c1d5df5ba6980dd6c66af5e92c687825`)

---

# 1. Mục tiêu

Sprint 12 phục hồi và nâng cấp luồng phiên âm có ngữ cảnh, đồng thời bổ sung khả năng nhập video từ URL mà **không tạo thêm một pipeline xử lý media thứ hai**.

Sprint gồm hai năng lực phối hợp với nhau:

1. **Phiên âm theo ngữ cảnh** — Project lưu dữ liệu Ngữ cảnh + Thuật ngữ; tại thời điểm bắt đầu một lượt Generate mới, dữ liệu này được biên dịch có giới hạn thành Whisper `initial_prompt`.
2. **Nhập video từ URL** — URL bên ngoài phải được resolve/tải xuống thành file media cục bộ, kiểm tra hợp lệ và finalize nguyên tử trước; sau đó mới tái sử dụng các luồng Project, Queue, VideoPlayer, Timing Draft, Full Subtitle, Recovery và Artifact hiện có.

Ba nguyên tắc trung tâm:

> Audio là nguồn sự thật cuối cùng. Ngữ cảnh chỉ giúp thiên vị nhận dạng từ vựng, không được phép sáng tác lại lời thoại.

> URL chỉ là nguồn nhập. Media chuẩn của Project luôn là một file cục bộ đã được xác thực.

> Import thất bại hoặc bị hủy phải để lại **0 side-effect canonical lên Project**.

---

# 2. Ngoài phạm vi Sprint 12

Sprint 12 **không** bao gồm:

- Local LLM hậu xử lý, dịch thuật hoặc rewrite lời thoại.
- Viết lại subtitle theo lore/phong cách nhân vật.
- Thay thế source video của Project đang tồn tại.
- Tải playlist hàng loạt.
- Ghi livestream.
- Bypass DRM.
- UI đăng nhập/cookies.
- Đọc cookie từ trình duyệt.
- Lưu credential.
- Tải subtitle track từ website.
- Phát URL trực tiếp bằng VideoPlayer.
- Transcribe URL trực tiếp bằng Whisper.
- Tạo pipeline Timing/ASR riêng cho URL.
- Cho người dùng truyền arbitrary yt-dlp arguments, output template, downloader hoặc shell postprocessor.
- Transcode toàn bộ media chỉ để phục vụ import.
- Glossary editor dạng chip/tag phức tạp.
- Tự động garbage-collect media queue-only đã tải thành công.

---

# 3. Ràng buộc kiến trúc hiện hữu

Sprint 12 mở rộng kiến trúc hiện tại, không thay thế các owner đã có:

- `ProjectService` sở hữu vòng đời và persistence canonical của Project.
- `Project.source.path` + fingerprint vẫn là định danh media canonical.
- `QueueManager.add_video()` chỉ nhận path file cục bộ đã tồn tại.
- `SubtitleGenerationRequest.video_path` vẫn chỉ là local path.
- `FasterWhisperService` tiếp tục xử lý local media qua pipeline FFmpeg hiện có.
- Timing Draft và Full Subtitle tái sử dụng source workflow hiện tại.
- `RevisionTracker` vẫn là nguồn sự thật cho dirty state.
- `RecoveryManager` bảo vệ canonical working state chưa Save.
- Worker chỉ thực thi; Service sở hữu transaction; MainWindow chỉ điều phối ứng dụng/UI.
- `ui/Gui.py` không được chứa HTTP, yt-dlp, ffprobe, staging hoặc thuật toán prompt.
- Không tạo thêm subtitle domain model mới.

---

# 4. Các invariant đã khóa

## 4.1. Local-media-first

Mọi URL đều phải đi qua:

```text
URL
→ resolve / download
→ media trong staging
→ validate media
→ atomic finalize
→ local canonical media
→ pipeline hiện có
```

Không được tạo các API production tương đương:

```text
load_url_video()
generate_from_url()
timing_from_url()
```

## 4.2. Không thay source Project hiện tại

URL Import chỉ được phép:

- tạo **New Project**, hoặc
- tạo local media bền vững rồi **Add to Queue**.

Không có chức năng Replace Source trong Sprint 12.

## 4.3. 0 canonical side-effect trước finalize

Trước khi media finalize thành công:

```text
ProjectService untouched
QueueManager untouched
VideoPlayer untouched
Recovery untouched
ArtifactStore untouched
```

Chỉ staging directory/file được phép tồn tại.

## 4.4. Project chỉ lưu dữ liệu người dùng

Project persistence chỉ lưu:

```text
context: str
glossary: list[str]
```

Project không lưu compiled prompt theo model.

## 4.5. Prompt là dữ liệu dẫn xuất và bất biến theo transaction

```text
Project.transcription_context
→ PromptContextBuilder
→ CompiledPromptContext
→ SubtitleGenerationRequest.prompt_context
```

Khi generation transaction đã bắt đầu, compiled prompt của transaction đó bất biến cho đến khi kết thúc/resume.

## 4.6. Resume giữ prompt cũ

Nếu lượt Generate bắt đầu bằng prompt `P`, sau đó Project Context đổi thành `P2`, Resume lượt cũ vẫn phải dùng `P`.

Chỉ lượt Generate mới được phép compile và dùng `P2`.

## 4.7. Glossary luôn ưu tiên trước Context

Trong token budget:

1. Glossary được cấp ngân sách trước theo stable order.
2. Phần ngân sách còn lại mới dùng cho Context.
3. Context bị truncate trước các Glossary term đã accept.
4. Không cắt nửa một Glossary term.
5. Nếu riêng Glossary đã vượt budget thì giữ deterministic first-N.

## 4.8. Audio là nguồn sự thật

Context chỉ được truyền vào Whisper qua `initial_prompt`.

Không có Local LLM rewrite trong Sprint 12.

Timing Draft là VAD-only nên không consume Context.

## 4.9. Recovery phải bảo vệ Context/Glossary chưa Save

Edit Context/Glossary là canonical working-state edit, do đó phải:

- tăng đúng một logical external revision;
- khiến session dirty;
- được autosave vào recovery snapshot;
- sống sót qua crash restore;
- vẫn dirty sau restore cho đến explicit Save.

## 4.10. Atomic media acceptance

```text
adapter output trong staging
→ MediaProbe validate
→ os.replace(..., canonical_path)
→ chỉ sau đó mới trả MediaImportResult
```

`.part`, fragments và temp file do adapter tạo chỉ là implementation detail, không phải durability contract của app.

## 4.11. Worker/Service boundary

`MediaImportWorker` chỉ execute `MediaImportService`.

`MediaImportService` không phụ thuộc vào:

- `ProjectService`
- `QueueManager`
- `MainWindow`
- `VideoPlayer`
- `FasterWhisperService`
- Timing subsystem
- `ArtifactStore`

## 4.12. Network security boundary

Chỉ nhận:

```text
http://
https://
```

Phải chặn:

- loopback;
- private RFC1918 / IPv6 private;
- link-local;
- multicast;
- unspecified;
- reserved/non-public ranges phù hợp;
- redirect sang địa chỉ bị chặn;
- hostname public nhưng DNS resolve/rebind sang địa chỉ private/local.

TLS verification không được tắt.

---

# 5. Project Schema v2

Domain model mới:

```python
@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)
```

Project v2:

```text
Project
├── project_id
├── name
├── created_at
├── updated_at
├── source
├── transcription_context
│   ├── context
│   └── glossary[]
├── state
└── schema_version = 2
```

`project.json` lưu `transcription_context`.

`state.json` và `workspace.json` không sở hữu dữ liệu này.

Ví dụ:

```json
{
  "schema_version": 2,
  "project_id": "uuid",
  "name": "Example",
  "source": {
    "path": "...",
    "fingerprint": "..."
  },
  "transcription_context": {
    "context": "Trận chiến tại Demacia...",
    "glossary": ["Demacia", "Garen", "Lux", "Petricite"]
  }
}
```

---

# 6. Migration Project v1 → v2

Nếu mở Project v1 không có `transcription_context`, runtime tạo mặc định trong RAM:

```text
context = ""
glossary = []
```

Open/migrate không được tự ghi lại canonical file.

Project chỉ chuyển thành shape v2 trên disk khi người dùng explicit Save.

---

# 7. Chuẩn hóa Glossary

Canonical normalization:

1. trim whitespace đầu/cuối;
2. bỏ entry rỗng;
3. deduplicate bằng `casefold()`;
4. giữ cách viết hiển thị của occurrence đầu tiên;
5. giữ stable input order;
6. không sort ẩn.

Ví dụ:

```text
Demacia
demacia
 DEMACIA
```

trở thành:

```text
Demacia
```

---

# 8. Semantics khi edit Context

```text
user gõ
→ debounce 300–500 ms hoặc focus-out
→ commit logical value
→ Project.transcription_context cập nhật
→ ProjectService.mark_dirty()
→ RevisionTracker.record_external_change()
→ Recovery autosave eligible
```

Không được tăng revision theo từng keystroke.

Không có nút `Save Context` riêng.

`Ctrl+S` tiếp tục là canonical Save theo save routing hiện có.

---

# 9. Mở rộng Recovery schema

`RecoveryWorkingState` thêm:

```text
transcription_context
├── context
└── glossary[]
```

Recovery chỉ lưu raw canonical working data.

Không duplicate compiled `prompt_context` vào recovery snapshot; compiled prompt thuộc generation checkpoint nếu có generation đang chạy.

---

# 10. PromptContextBuilder

Subsystem mới:

```text
core/transcription/
├── prompt_context_builder.py
└── token_counter.py
```

Contract:

```python
PromptContextBuilder.build(
    transcription_context: TranscriptionContext,
    max_tokens: int = 180,
) -> CompiledPromptContext
```

Token counter được dependency-inject qua protocol nhỏ:

```python
class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...
```

`DEFAULT_PROMPT_BUDGET = 180` là runtime policy bảo thủ, không phải dữ liệu persisted và không khẳng định mọi model đều có cùng hard limit.

---

# 11. CompiledPromptContext

Model immutable đề xuất:

```text
CompiledPromptContext
├── text
├── token_count
├── max_tokens
├── glossary_items_used
├── glossary_items_dropped
├── context_truncated
└── truncated
```

UI được phép hiển thị diagnostic nhưng không cho sửa compiled text trực tiếp.

---

# 12. Thuật toán compile prompt

```text
normalize glossary
→ thêm term theo stable order nếu còn fit
→ khóa các term đã accept
→ dùng budget còn lại cho Context
→ ưu tiên truncate tại sentence boundary
→ nếu không được thì whitespace boundary
→ hard boundary chỉ là phương án cuối
→ trả text + diagnostics
```

Format runtime khuyến nghị:

```text
Terminology: Demacia, Noxus, Garen, Lux, Petricite.
Context: Trận chiến tại Demacia. Garen đang nói chuyện với Lux.
```

Nếu Context và Glossary đều rỗng:

```text
CompiledPromptContext.text == ""
```

---

# 13. Contract Contextual Generation

`SubtitleGenerationRequest` thêm:

```python
prompt_context: str = ""
```

Luồng generation mới:

```text
Generate
→ đọc Project.transcription_context
→ compile đúng một lần
→ ghi compiled text vào request
→ request/checkpoint sở hữu snapshot này
→ FasterWhisperService
→ model.transcribe(..., initial_prompt=request.prompt_context)
```

Nếu prompt rỗng thì omit `initial_prompt` hoặc truyền `None` theo API Faster-Whisper.

Request không giữ raw Context/Glossary.

---

# 14. Checkpoint / Resume

```text
start với prompt P
→ checkpoint persist request có P
→ user sửa Project Context thành P2
→ Resume checkpoint cũ
→ vẫn dùng P
→ lượt Generate mới mới dùng P2
```

Đây là invariant bắt buộc để batch output deterministic và debug được.

---

# 15. UI/UX Context

Context thuộc Project hiện tại và nằm ở Right Inspector:

```text
Right Inspector
├── Subtitle
├── Generate
└── Context
```

Panel:

```text
Transcription Context

Context
[multiline editor]

Glossary
[one term per line]

Prompt usage
6/6 terms · ~72/180 tokens
✓ Đã dùng toàn bộ thuật ngữ
```

Nếu truncate:

```text
⚠ Chỉ dùng 8/14 thuật ngữ
⚠ Context đã bị rút gọn
```

Có thể có `Preview compiled prompt` dạng read-only.

`SubtitleGenerationPanel` chỉ hiển thị trạng thái ngắn + action `Edit Context`, không duplicate editor.

Full Subtitle dùng Context.

Timing Draft không dùng Context.

---

# 16. Kiến trúc Media Import

```text
UI
→ MediaImportWorker
→ MediaImportService
→ URLClassifier
→ DirectHTTPAdapter / YtDlpAdapter
→ staging output
→ MediaProbe
→ atomic finalize
→ MediaImportResult
→ MainWindow orchestration
→ ProjectService hoặc QueueManager
```

Cấu trúc mới:

```text
core/media_import/
├── media_import_service.py
├── media_import_models.py
├── media_import_errors.py
├── network_safety.py
├── media_probe.py
├── url_classifier.py
└── adapters/
    ├── downloader_adapter.py
    ├── yt_dlp_adapter.py
    └── direct_http_adapter.py
```

---

# 17. MediaImportResult / Progress

Result immutable:

```text
MediaImportResult
├── local_path
├── original_url
├── filename
├── size_bytes
├── media_type
└── metadata
```

Metadata có thể gồm:

```text
duration_ms
width
height
codec
container
fps
```

Progress stage:

```text
RESOLVING
DOWNLOADING
VALIDATING
FINALIZING
```

Payload:

```text
MediaImportProgress
├── stage
├── downloaded_bytes
├── total_bytes | None
├── speed_bytes_per_sec | None
├── eta_seconds | None
└── percent | None
```

Unknown total size là case hợp lệ và UI dùng progress indeterminate.

---

# 18. Chính sách chọn Adapter

```text
URL
→ validate public HTTP(S)
→ classify

obvious direct media?
├─ yes
│  → DirectHTTPAdapter
│  → HTTP/network/media failure thật: STOP
│  → response thực ra là page/non-media: có thể thử yt-dlp
│
└─ no
   → YtDlpAdapter
   → UnsupportedURL / no extractor: cho phép DirectHTTP fallback
   → auth/network/geo/DRM/...: giữ lỗi gốc, KHÔNG fallback mù
```

Extension và Content-Type chỉ là routing hint, không phải media trust boundary.

---

# 19. DirectHTTPAdapter

Dùng `requests` streaming trong worker thread; không thêm asyncio runtime.

Yêu cầu:

- stream theo chunk xuống disk;
- không load toàn bộ media vào RAM;
- connect/read timeout hữu hạn;
- redirect limit hữu hạn;
- TLS verify bật;
- validate URL/IP trước connection và sau mỗi redirect;
- chống DNS rebinding/TOCTOU gần connection nhất có thể;
- cancellation cooperative trong vòng lặp streaming;
- map lỗi mạng sang error taxonomy;
- không tự lấy Authorization/cookie từ browser.

---

# 20. YtDlpAdapter

Dùng yt-dlp Python API:

```python
yt_dlp.YoutubeDL(options)
```

Không dùng shell command string.

Policy cố định:

```text
noplaylist = True
single video only
no cookies
no browser cookie extraction
no credentials
no arbitrary user output template
no custom external downloader
no arbitrary shell postprocessor
```

Format ưu tiên:

```text
bestvideo*+bestaudio/best
```

FFmpeg được phép merge streams.

Sprint 12 không bắt buộc transcode mọi nguồn về MP4.

Resolved network target do yt-dlp sử dụng vẫn phải tuân theo public-network safety policy ở mức adapter cho phép.

---

# 21. Media Validation Gate

Trước finalize, `MediaProbe` bắt buộc kiểm tra:

```text
file exists
size > 0
ffprobe succeeds
has video stream
duration > 0
```

Audio-only → `NO_VIDEO_STREAM`.

Trust boundary cuối là cấu trúc media do ffprobe xác nhận, không phải extension/Content-Type.

---

# 22. Project-owned Media Storage

Với New Project từ URL:

```text
<Project>.ai-subtitle/
├── project.json
├── state.json
├── workspace.json
├── media/
│   └── source.<validated-ext>
└── artifacts/
```

Trong lúc import chỉ có staging:

```text
<Project>.ai-subtitle/
└── media/
    └── .staging/
        └── <download-id>/
```

Canonical Project file chưa được tạo trước finalize thành công.

---

# 23. Ruling Precompute Bundle Path

Luồng New Project từ URL:

```text
user chọn root + project name
→ tính trước <Project>.ai-subtitle path
→ chỉ tạo media/.staging/<id>
→ download
→ validate
→ atomic finalize media
→ ProjectService.create_project(...)
→ tạo/switch Recovery session
→ existing Player/Workspace
```

Failure/cancel:

- xóa staging;
- dọn thư mục rỗng an toàn;
- không có `project.json`;
- không có `state.json`;
- không có Artifact manifest;
- không có Recovery session canonical.

---

# 24. Queue-only URL Storage

`Add to Queue` từ URL dùng durable app-owned storage, không dùng `%TEMP%` và không tạo fake Project:

```text
%LOCALAPPDATA%/AI Subtitle Studio/media_imports/
└── <import-id>/
    ├── .staging/
    └── source.<validated-ext>
```

Path thật do `RuntimePaths` sở hữu; media import không hard-code `%LOCALAPPDATA%`.

Queue-only workflow:

```text
URL
→ RuntimePaths media_imports staging
→ download + validate + atomic finalize
→ QueueManager.add_video(finalized_local_path)
```

Ruling lifecycle Sprint 12:

- file queue-only đã finalize thành công là durable;
- remove Queue item **không** tự xóa underlying file;
- auto cache garbage collection là non-goal.

Ưu tiên data safety hơn aggressive disk cleanup.

---

# 25. Atomic Finalization

Áp dụng giống nhau cho Project media và Queue-only media:

```text
adapter hoàn tất staged media
→ MediaProbe validate
→ chọn app-controlled filename/extension
→ os.replace(staged_media, canonical_path)
→ fsync parent directory nếu thực tế hỗ trợ
→ trả MediaImportResult
```

Nếu `os.replace` fail:

- không chấp nhận canonical media;
- không mutate Project/Queue;
- trả `FINALIZE_FAILED`.

---

# 26. Workflow New Project từ URL

```text
Import Video from URL
→ URL/public-network validation
→ precompute Project bundle staging path
→ MediaImportWorker
→ RESOLVING
→ DOWNLOADING
→ VALIDATING
→ FINALIZING
→ MediaImportResult(local_path)
→ ProjectService.create_project(...)
→ switch/create Recovery session
→ existing metadata loader
→ existing VideoPlayer
→ existing Workspace
→ Timing Draft available
→ Full Subtitle available
```

Không có URL-specific Project type.

---

# 27. Workflow Add to Queue

```text
Import Video from URL
→ chọn Add to Queue
→ RuntimePaths media_imports/<id> staging
→ MediaImportWorker
→ MediaImportResult(local_path)
→ QueueManager.add_video(local_path)
→ existing Queue workflow
```

`QueueManager` vẫn local-path-only.

---

# 28. URL Import UI

Một dialog dùng chung:

```text
ui/dialogs/media_import_dialog.py
```

Entry point có thể gồm:

```text
File > Import > Video from URL...
Queue > URL
```

Cả hai đều mở cùng implementation.

State ban đầu:

```text
URL [................................]

Nhập dưới dạng:
● New Project
○ Add to Queue

Project Location [Browse...]   # chỉ New Project
Project Name     [...]         # chỉ New Project

[Hủy] [Import]
```

Running state machine:

```text
IDLE
→ RESOLVING
→ DOWNLOADING
→ VALIDATING
→ FINALIZING
→ SUCCEEDED
```

Failure:

```text
running → FAILED
```

Cancel:

```text
running → CANCELLING → CANCELLED
```

Đóng dialog khi worker đang chạy phải trigger cooperative cancel/cleanup, không bỏ worker mồ côi.

---

# 29. MainWindow / Module Boundaries

Files mới ở UI/worker:

```text
ui/components/transcription_context_panel.py
ui/dialogs/media_import_dialog.py
workers/media_import_worker.py
```

MainWindow chỉ được:

```text
mở dialog
start worker
nhận result
call ProjectService / QueueManager
switch active workspace
```

MainWindow không được sở hữu:

```text
HTTP requests
yt-dlp config
ffprobe invocation
staging mechanics
prompt token/truncation algorithm
```

Đây là cleanup trách nhiệm có mục tiêu, không phải broad refactor.

---

# 30. Bảo mật — URL, DNS, Redirect, SSRF

Allowed scheme:

```text
http
https
```

Rejected scheme:

```text
file
ftp
smb
data
javascript
custom schemes
```

Đối với HTTP(S), importer phải reject target resolve tới:

```text
loopback
private
link-local
multicast
unspecified
reserved/non-public phù hợp
```

Yêu cầu:

1. resolve hostname trước connection nếu adapter cho phép;
2. validate mọi resolved candidate IP;
3. validate từng redirect destination;
4. validate actual resolved/connected target càng sát thời điểm connection càng tốt để chống DNS rebinding/TOCTOU;
5. không bao giờ tắt TLS verification.

Áp dụng về nguyên tắc cho cả DirectHTTP và yt-dlp mediated requests.

---

# 31. Bảo mật — Path Confinement

Không bao giờ tin remote metadata làm filesystem path:

```text
video title
URL basename
Content-Disposition filename
yt-dlp extractor title
```

Canonical filename do app quyết định:

```text
source.mp4
source.webm
source.mkv
```

Trước mọi write/finalize:

```text
resolved output path MUST be descendant of configured target directory
```

Traversal/confinement violation → security failure.

---

# 32. Bảo mật — Shell Execution

FFmpeg/ffprobe dùng argument array và:

```text
shell=False
```

Cấm:

```python
subprocess.run(f"ffprobe {user_input}", shell=True)
```

URL không được interpolate vào shell command.

---

# 33. Bảo mật — Log

Log được phép có:

- adapter name;
- stage;
- hostname/path đã redact;
- HTTP status;
- exception type.

Log không được chứa:

- cookies;
- Authorization headers;
- credentials;
- browser session data;
- signed/auth query string đầy đủ.

Mặc định redact query và fragment khỏi URL trước khi log.

---

# 34. Error Taxonomy

```text
INVALID_URL
UNSAFE_URL
UNSUPPORTED_URL
NETWORK_ERROR
TIMEOUT
HTTP_ERROR
AUTH_REQUIRED
DRM_OR_PROTECTED
MEDIA_NOT_FOUND
INVALID_MEDIA
NO_VIDEO_STREAM
DISK_FULL
PERMISSION_DENIED
DOWNLOAD_CANCELLED
FINALIZE_FAILED
UNKNOWN
```

`UNSAFE_URL` bao gồm:

- scheme bị cấm;
- local/private target;
- unsafe redirect;
- network boundary violation liên quan.

Cancellation chủ động không hiển thị như error dialog đỏ.

---

# 35. Resource Protection / Cancellation

Download stream xuống disk, không buffer whole media vào RAM.

Nếu biết expected size, importer có thể preflight free disk.

`ENOSPC` → `DISK_FULL`.

Sprint 12 không đặt arbitrary fixed max media size.

Cancellation:

```text
UI Cancel
→ worker cancellation token
→ adapter quan sát token
→ stop network/yt-dlp cooperatively
→ close handle/resource
→ delete staging session
→ emit cancelled
```

Không có downstream canonical mutation khi cancel.

---

# 36. Cấu trúc thư mục dự kiến

```text
core/
├── project/
│   ├── project.py                         MODIFY
│   └── transcription_context.py           NEW
├── transcription/
│   ├── __init__.py                        NEW
│   ├── prompt_context_builder.py          NEW
│   └── token_counter.py                   NEW
├── media_import/
│   ├── __init__.py                        NEW
│   ├── media_import_service.py            NEW
│   ├── media_import_models.py             NEW
│   ├── media_import_errors.py             NEW
│   ├── network_safety.py                  NEW
│   ├── media_probe.py                     NEW
│   ├── url_classifier.py                  NEW
│   └── adapters/
│       ├── __init__.py                    NEW
│       ├── downloader_adapter.py           NEW
│       ├── yt_dlp_adapter.py               NEW
│       └── direct_http_adapter.py          NEW
├── runtime/
│   └── runtime_paths.py                    MODIFY
├── subtitle_generation/
│   ├── subtitle_generation_request.py      MODIFY
│   ├── faster_whisper_service.py           MODIFY
│   └── checkpoint serialization            MODIFY khi cần
└── recovery/
    ├── recovery_models.py                  MODIFY
    └── recovery_validator.py               MODIFY

ui/
├── components/
│   └── transcription_context_panel.py      NEW
├── dialogs/
│   └── media_import_dialog.py              NEW
├── subtitle_generation_panel.py            MODIFY
└── Gui.py                                  orchestration only

workers/
└── media_import_worker.py                  NEW

tests/
├── test_transcription_context.py
├── test_prompt_context_builder.py
├── test_contextual_whisper.py
├── test_media_import_service.py
├── test_media_import_adapters.py
├── test_media_import_ui.py
└── test_sprint12_end_to_end.py
```

---

# 37. Kiểm thử chấp nhận — Contextual Transcription

## TC107 — Migration Project v1

```text
load Project v1
→ TranscriptionContext rỗng trong RAM
→ canonical file không bị rewrite
```

## TC108 — Round-trip Project v2

```text
save/open v2
→ Context giữ nguyên
→ Glossary ở canonical normalized form
→ stable order được giữ
```

## TC109 — Glossary priority

```text
prompt vượt budget
→ Context truncate trước Glossary đã accept
```

## TC110 — Glossary tự vượt budget

```text
first-N deterministic
→ không partial term
```

## TC111 — Context rỗng

```text
compiled prompt == ""
→ Whisper không nhận effective initial_prompt
```

## TC112 — Context đi tới Whisper

```text
compiled request.prompt_context
→ exact initial_prompt của FasterWhisper
```

## TC113 — Resume giữ original prompt

```text
start bằng P
→ checkpoint
→ Project đổi thành P2
→ resume vẫn dùng P
```

## TC114 — Revision + Recovery participation

```text
logical Context/Glossary commit
→ đúng một external revision
→ dirty
→ recovery snapshot chứa edit
```

## TC115 — Crash restore Context

```text
unsaved Context/Glossary
→ durable recovery snapshot
→ crash/restore
→ dữ liệu được phục hồi
→ vẫn dirty cho đến explicit Save
```

---

# 38. Kiểm thử chấp nhận — Media Import

## TC116 — Direct media

```text
direct MP4/compatible URL
→ DirectHTTPAdapter
→ validated atomic local file
```

## TC117 — Website được hỗ trợ

```text
supported website URL
→ YtDlpAdapter
→ validated atomic local media
```

## TC118 — Unsupported extractor fallback

```text
yt-dlp UnsupportedURL/no extractor
→ DirectHTTP fallback được phép
```

## TC119 — Không che lỗi thật

```text
auth/network/DRM/geo error
→ giữ classified original error
→ không blind fallback
```

## TC120 — Cancel giữa download

```text
cancel
→ staging removed
→ không Project/Queue mutation
```

## TC121 — Network failure cleanup

```text
network failure
→ staging removed
→ canonical target absent
```

## TC122 — Invalid media

```text
download complete
→ ffprobe invalid/no video
→ không downstream mutation
```

## TC123 — Finalize failure

```text
os.replace fail
→ không canonical media accepted
→ không Project/Queue mutation
```

## TC124 — New Project SourceInfo

```text
URL import thành công
→ Project.source.path = finalized local media
→ fingerprint sinh từ local media
```

## TC125 — Tái sử dụng Player

```text
successful import
→ existing VideoPlayer nhận cùng finalized local path
```

## TC126 — Tái sử dụng Timing Draft

```text
successful import
→ existing Timing Draft chạy trên Project.source.path
```

## TC127 — Tái sử dụng Full Subtitle

```text
SubtitleGenerationRequest.video_path == Project.source.path
```

## TC128 — Source guard sau reopen

```text
Save/close/reopen
→ source fingerprint vẫn valid
```

## TC129 — Full URL E2E

```text
URL
→ adapter
→ staging
→ validate
→ finalize
→ Project
→ Player
→ Timing Draft
→ Full Subtitle
→ Save
→ close
→ reopen
→ valid source guard
```

## TC130 — Queue-only durable storage

```text
URL
→ app-owned media_imports/<id>
→ atomic finalize
→ Queue nhận local path
→ không fake Project
```

## TC131 — SSRF / unsafe redirect guard

```text
loopback/private/link-local target hoặc redirect
→ UNSAFE_URL
→ reject trước canonical download acceptance
```

CI dùng injectable fake/mock cho network adapter và media probe; không phụ thuộc Internet thật.

---

# 39. Regression Gates

Sprint 12 không được regression:

- Sprint 9 generation/checkpoint/resume.
- Sprint 10 canonical segment schema/editing/undo.
- Sprint 11 dirty state, recovery snapshot, source mismatch guard, recovery handoff, close matrix, single-instance IPC, explicit Save và Export != Save.

Final verification bắt buộc:

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
```

CI chỉ thay đổi nếu discovery/dependency hiện tại không chạy được test Sprint 12.

---

# 40. Dependency mới

Production dependencies:

```text
yt-dlp
requests
```

Nếu `requests` đã có transitively vẫn phải khai báo explicit vì production code import trực tiếp.

FFmpeg/ffprobe tiếp tục là runtime dependency theo `RuntimePaths` hiện có.

Không thêm HTTP asyncio dependency.

---

# 41. Tóm tắt ownership

```text
TranscriptionContext
→ dữ liệu domain do user sở hữu

PromptContextBuilder
→ compiler deterministic cho prompt dẫn xuất

SubtitleGenerationRequest
→ immutable generation transaction snapshot

FasterWhisperService
→ ASR adapter; chỉ consume initial_prompt

MediaImportDialog
→ presentation + state machine UI

MediaImportWorker
→ bridge thực thi background

MediaImportService
→ transaction URL → local media

URLClassifier
→ routing hint

NetworkSafetyPolicy
→ URL/DNS/IP/redirect/SSRF boundary

YtDlpAdapter / DirectHTTPAdapter
→ download mechanics

MediaProbe
→ media trust boundary

MainWindow
→ application orchestration

ProjectService
→ canonical Project lifecycle

QueueManager
→ queue lifecycle

RecoveryManager / RevisionTracker
→ durability + dirty truth
```

---

# 42. Các ruling cuối cùng đã khóa

1. Contextual Whisper chỉ dùng `initial_prompt`; không Local LLM.
2. Project lưu Context + Glossary, không lưu compiled prompt.
3. Prompt budget 180 là runtime policy, không phải persisted schema.
4. Glossary ưu tiên trước Context.
5. Resume giữ original compiled prompt.
6. URL import luôn download-first/local-file-first.
7. `MediaImportService` độc lập với Project/Queue/Player/Whisper.
8. yt-dlp + Direct HTTP nằm sau adapter boundary.
9. DirectHTTP không blind fallback cho mọi lỗi yt-dlp.
10. Media phải qua ffprobe trước canonical acceptance.
11. Không Replace Source Project hiện tại.
12. New Project chỉ được tạo sau media finalize thành công.
13. Fail/cancel tạo 0 canonical Project side-effect.
14. Queue-only media dùng durable `RuntimePaths.media_imports`.
15. MainWindow chỉ orchestration.
16. Chỉ public HTTP(S).
17. Chặn SSRF, unsafe redirect và DNS rebinding ở mức adapter có thể bảo đảm.
18. Không cookie/credential/DRM bypass/arbitrary shell hook.
19. Path confinement và `shell=False` bắt buộc.
20. Context/Glossary edit tham gia RevisionTracker + Recovery.
21. Timing Draft không consume Context.
22. Sau URL finalize phải tái sử dụng pipeline local Project/Player/Timing/Full Subtitle hiện có.

---

# 43. Definition of Done

## Contextual Transcription

```text
✅ Project v2 persist Context + Glossary
✅ Project v1 backward-compatible
✅ edit Context/Glossary được revision-track
✅ Recovery bảo vệ unsaved Context/Glossary
✅ PromptContextBuilder deterministic + bounded
✅ Glossary priority đúng contract
✅ FasterWhisper nhận initial_prompt
✅ empty context không tạo effective prompt
✅ checkpoint/resume giữ original prompt transaction
```

## Media Import

```text
✅ URL dialog hỗ trợ New Project / Add to Queue
✅ yt-dlp adapter qua Python API
✅ DirectHTTP streaming
✅ classified routing/fallback
✅ progress + cancel không block UI
✅ staging cô lập
✅ ffprobe validation
✅ app-controlled atomic finalize
✅ fail/cancel = 0 canonical Project side-effect
✅ successful import sinh local SourceInfo/fingerprint
✅ VideoPlayer reuse
✅ Timing Draft reuse
✅ Full Subtitle reuse
✅ source guard valid sau Save/reopen
✅ queue-only media ở durable app storage
```

## Security / Architecture

```text
✅ public HTTP(S)-only
✅ TLS verify ON
✅ SSRF/private/local/unsafe redirect guard
✅ path traversal prevented
✅ shell=False subprocess
✅ không cookie/credential/DRM bypass surface
✅ URL query sensitive được redact trong log
✅ MediaImportService không phụ thuộc Project/UI/Whisper
✅ MainWindow chỉ orchestration
```

## Verification

```text
✅ TC107–TC131 pass
✅ full regression suite pass
✅ compileall pass
✅ worktree sạch
✅ PR review không còn Critical/Important unresolved
```
