# Sprint 12 — Contextual Transcription & Media Import

**Status:** Locked Design Spec — pending final user review  
**Date:** 2026-09-02  
**Target branch:** `sprint-12`  
**Base:** `master` after Sprint 11 (`4f827b32c1d5df5ba6980dd6c66af5e92c687825`)  

## 1. Goal

Sprint 12 restores and strengthens contextual transcription while adding secure URL-based video import without creating a second media-processing pipeline.

The sprint introduces two coordinated capabilities:

1. **Contextual Transcription** — project-owned Context + Glossary data is compiled deterministically into a bounded Whisper `initial_prompt` for each new generation transaction.
2. **Media Import from URL** — external URLs are resolved/downloaded into validated local project-owned media first; only then are the existing Project, VideoPlayer, Timing Draft, Full Subtitle, Recovery, and Artifact workflows reused.

The central rules are:

> Audio remains the source of truth. Context only biases transcription.

> URLs are import sources, never canonical project media. Canonical media is always a validated local file.

> Failed or cancelled URL import must leave zero Project side effects.

---

## 2. Non-goals

Sprint 12 does **not** include:

- Local LLM post-processing or translation.
- Rewriting subtitle text according to lore/style.
- Replacing the source video of an existing project.
- Playlist/batch playlist download.
- Livestream recording.
- DRM bypass.
- Authentication/cookies UI.
- Browser-cookie extraction.
- Credential storage.
- Downloading remote subtitle tracks.
- Direct URL playback in VideoPlayer.
- Direct URL transcription in Whisper.
- A second URL-specific Timing/ASR pipeline.
- Arbitrary yt-dlp command arguments or user-defined postprocessors.
- Media transcoding solely for import compatibility.
- A chip/tag-heavy glossary editor.

---

# 3. Existing Architecture Constraints

Sprint 12 extends the existing architecture rather than replacing it:

- `ProjectService` owns canonical Project lifecycle and project persistence.
- `Project.source.path` and source fingerprint remain the canonical media identity.
- `QueueManager.add_video()` accepts existing local filesystem paths.
- `SubtitleGenerationRequest.video_path` remains a local file path.
- `FasterWhisperService` consumes local media through FFmpeg batch extraction.
- Timing Draft and Full Subtitle already share existing project/source workflows.
- `RevisionTracker` remains the source of truth for working-state dirtiness.
- `RecoveryManager` protects unsaved canonical working state.
- Workers execute; Services own domain transactions; MainWindow orchestrates UI/application workflows.
- `Gui.py` is already large and must not absorb media downloader or prompt compilation internals.

No new subtitle domain model is introduced.

---

# 4. Locked Invariants

## 4.1 Local-media-first invariant

Every imported URL must become a validated local media file before any Project/Queue/Player/Timing/ASR workflow begins.

```text
URL
→ resolve/download
→ local staging media
→ validate media
→ atomic finalize
→ local canonical media
→ existing application pipeline
```

Forbidden production APIs include conceptual equivalents of:

```text
load_url_video()
generate_from_url()
timing_from_url()
```

## 4.2 No source replacement invariant

Sprint 12 never replaces the source video of an existing Project.

URL import may only:

- create a **New Project**, or
- download a local file and **Add to Queue**.

This avoids invalidating existing timing, subtitle artifacts, source fingerprints, and recovery provenance.

## 4.3 Failed import side-effect invariant

Before a URL import reaches successful atomic finalization:

```text
ProjectService untouched
QueueManager untouched
VideoPlayer untouched
Recovery untouched
```

A failed/cancelled import may create staging files/directories only. Those staging artifacts must be cleaned.

## 4.4 Context domain invariant

Project persistence stores only user-authored domain data:

```text
context
glossary[]
```

Project persistence never stores model-specific compiled prompt text.

## 4.5 Derived prompt invariant

`prompt_context` is derived per **new generation transaction** by `PromptContextBuilder`.

```text
Project.transcription_context
→ PromptContextBuilder
→ CompiledPromptContext
→ SubtitleGenerationRequest.prompt_context
```

The compiled prompt is immutable for the lifetime of that generation request/checkpoint.

## 4.6 Resume prompt invariant

If a generation starts with prompt `P`, then Project Context changes to `P2`, resuming the original generation still uses `P`.

Only a new generation transaction may use `P2`.

## 4.7 Glossary priority invariant

Within the configured prompt token budget:

1. Glossary terms are allocated first.
2. Remaining budget is used for Context.
3. Context is truncated before already-accepted glossary items.
4. A glossary item is never partially cut.
5. If the glossary alone exceeds budget, deterministic first-N retention is used.

## 4.8 Audio truth invariant

Context never invents dialogue or rewrites recognized speech.

Whisper receives Context only through `initial_prompt`.

No Local LLM is introduced in Sprint 12.

## 4.9 Recovery coverage invariant

Unsaved edits to Context or Glossary are canonical working-state edits and therefore must:

- mark `RevisionTracker` dirty;
- be eligible for recovery autosave;
- survive crash restore;
- remain dirty after restore until explicit Save.

## 4.10 Atomic media invariant

Downloaded media becomes canonical only after:

```text
download into staging
→ completed adapter output
→ MediaProbe validation
→ os.replace(..., canonical_media_path)
```

Partial/fragments created by adapters are implementation details, not the application's durability contract.

## 4.11 Worker/service boundary invariant

`MediaImportWorker` may execute `MediaImportService`, but must not create Projects or mutate Queue/Workspace directly.

`MediaImportService` must not depend on:

- `ProjectService`
- `QueueManager`
- `MainWindow`
- `VideoPlayer`
- `FasterWhisperService`
- `TimingBatchWorker`
- `ArtifactStore`

## 4.12 Security boundary invariant

Only `http://` and `https://` URLs are accepted.

Rejected schemes include:

```text
file://
ftp://
smb://
data:
javascript:
custom schemes
```

TLS verification remains enabled. External filenames/titles never control filesystem confinement.

---

# 5. Project Schema v2

Sprint 12 upgrades the Project model from schema v1 to v2 by adding project-owned transcription metadata.

```text
Project
├── project_id
├── name
├── created_at
├── updated_at
├── source
├── transcription_context
│   ├── context: str
│   └── glossary: list[str]
├── state
└── schema_version = 2
```

New domain model:

```python
@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)
```

`project.json` shape:

```json
{
  "schema_version": 2,
  "project_id": "uuid",
  "name": "Example",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "source": {
    "path": "...",
    "filename": "source.webm",
    "size_bytes": 0,
    "modified_at": 0.0,
    "fingerprint": "..."
  },
  "transcription_context": {
    "context": "Trận chiến tại Demacia...",
    "glossary": ["Demacia", "Garen", "Lux", "Petricite"]
  }
}
```

`state.json` and `workspace.json` do not own Context/Glossary.

---

# 6. Project v1 → v2 Migration

Opening a v1 Project with no `transcription_context` yields in-memory defaults:

```text
context = ""
glossary = []
```

Opening/migrating does **not** automatically rewrite canonical Project files.

The v2 structure is written only on explicit Project Save.

This preserves the Sprint 11 rule that loading/migrating state in RAM is not an implicit user commit.

---

# 7. Glossary Normalization

Before canonical commit, Glossary is normalized deterministically:

1. trim leading/trailing whitespace;
2. remove empty entries;
3. deduplicate using `casefold()`;
4. preserve the first occurrence's visible spelling;
5. preserve stable input order.

Example:

```text
Demacia
demacia
 DEMACIA
```

becomes:

```text
Demacia
```

No hidden alphabetical sorting is performed.

---

# 8. Context Edit Semantics

Context/Glossary are canonical Project working state.

UI editing follows:

```text
user edits
→ debounced commit or focus-out commit
→ Project.transcription_context updated
→ ProjectService.mark_dirty()
→ RevisionTracker.record_external_change()
→ Recovery autosave eligible
```

Recommended debounce window: **300–500 ms**.

The implementation must avoid one revision increment per keystroke during continuous typing.

There is no separate “Save Context” action. `Ctrl+S` remains canonical Project/Draft Save according to current application save routing.

---

# 9. Recovery Schema Extension

`RecoveryWorkingState` is extended to include unsaved transcription context:

```text
RecoveryWorkingState
├── existing canonical segments[]
├── existing workspace_state
└── transcription_context
    ├── context
    └── glossary[]
```

Recovery snapshot behavior:

```text
edit Context/Glossary
→ dirty revision
→ recovery timer
→ snapshot includes transcription_context
→ crash
→ restore Context/Glossary
→ recovered_dirty_baseline = true
```

Explicit Save clears the recovered dirty baseline under existing Sprint 11 semantics.

---

# 10. PromptContextBuilder

New subsystem:

```text
core/transcription/
├── prompt_context_builder.py
└── token_counter.py
```

Primary contract:

```python
PromptContextBuilder.build(
    transcription_context: TranscriptionContext,
    max_tokens: int = 180,
) -> CompiledPromptContext
```

The Builder receives a token-counter dependency implementing a small protocol such as:

```python
class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...
```

The Project model never hardcodes model token limits.

Default production budget for Sprint 12:

```text
DEFAULT_PROMPT_BUDGET = 180
```

This is a conservative runtime policy, not a persisted domain invariant.

---

# 11. CompiledPromptContext

Recommended immutable output model:

```text
CompiledPromptContext
├── text: str
├── token_count: int
├── max_tokens: int
├── glossary_items_used: int
├── glossary_items_dropped: int
├── context_truncated: bool
└── truncated: bool
```

The UI may use this model for diagnostics, but users cannot directly edit `CompiledPromptContext.text`.

---

# 12. Prompt Compilation Algorithm

Conceptual deterministic algorithm:

```text
normalize glossary
→ add glossary terms in stable order while they fit
→ reserve all accepted glossary terms
→ use remaining budget for Context
→ truncate Context at semantic boundary
→ return compiled text + diagnostics
```

Recommended compiled shape:

```text
Terminology: Demacia, Noxus, Garen, Lux, Petricite.
Context: Trận chiến tại Demacia. Garen đang nói chuyện với Lux.
```

Context truncation preference:

```text
sentence boundary
→ whitespace boundary
→ final hard boundary only if unavoidable
```

No accepted glossary term is split.

If no Context and no Glossary exist:

```text
CompiledPromptContext.text == ""
```

---

# 13. Contextual Generation Contract

`SubtitleGenerationRequest` gains:

```python
prompt_context: str = ""
```

The request contains only the **compiled prompt snapshot**, not raw Project Context/Glossary.

Generation flow:

```text
Generate clicked
→ Project.transcription_context
→ PromptContextBuilder.build(...)
→ SubtitleGenerationRequest(prompt_context=compiled.text)
→ SubtitleGenerationService
→ FasterWhisperService.transcribe_batch()
→ model.transcribe(..., initial_prompt=request.prompt_context)
```

If the prompt is empty, `initial_prompt` should be omitted or passed as `None` according to the Faster-Whisper API contract.

Timing Draft does not consume transcription Context because it is VAD-only.

---

# 14. Generation Checkpoint/Resume

Checkpoint serialization must preserve the original request's `prompt_context` so that resume remains transactionally deterministic.

```text
start generation using P
→ checkpoint stores request containing P
→ user edits Project Context to P2
→ resume old checkpoint
→ continue using P
```

A newly started generation after the edit compiles and uses P2.

---

# 15. Context UI/UX

Context belongs to the active Project and therefore appears in the Right Inspector rather than Global Settings.

Recommended tab/panel:

```text
Right Inspector
├── Subtitle
├── Generate
└── Context
```

Context panel contains:

```text
Transcription Context

Context
[multiline editor]

Glossary
[one term per line]

Prompt usage
6/6 terms · ~72/180 tokens
✓ All terminology included
```

If truncated:

```text
⚠ 8/14 glossary terms included
⚠ Context truncated
```

Optional read-only action:

```text
Preview compiled prompt
```

The compiled prompt is never user-editable.

---

# 16. Generate Panel Integration

`SubtitleGenerationPanel` does not duplicate Context/Glossary editors.

It may show compact diagnostics:

```text
Context
✓ 6 glossary terms
✓ Context enabled
~72/180 prompt tokens
[Edit Context]
```

Full Subtitle uses Context.

Timing Draft explicitly does not.

---

# 17. Media Import Architecture

New subsystem:

```text
core/media_import/
├── media_import_service.py
├── media_import_models.py
├── media_import_errors.py
├── media_probe.py
├── url_classifier.py
└── adapters/
    ├── downloader_adapter.py
    ├── yt_dlp_adapter.py
    └── direct_http_adapter.py
```

Execution flow:

```text
UI
→ MediaImportWorker
→ MediaImportService
→ URLClassifier
→ DownloaderAdapter
→ staging output
→ MediaProbe
→ atomic finalize
→ MediaImportResult
→ MainWindow orchestration
→ ProjectService / QueueManager
```

`MediaImportService` ends responsibility when it returns a valid finalized local file.

---

# 18. MediaImportResult

Recommended immutable result:

```text
MediaImportResult
├── local_path
├── original_url
├── filename
├── size_bytes
├── media_type
└── metadata
```

Metadata may include:

```text
duration_ms
width
height
codec
container
fps
```

No Project object is returned by `MediaImportService`.

---

# 19. Media Import Progress Contract

Progress model stages:

```text
RESOLVING
DOWNLOADING
VALIDATING
FINALIZING
```

Recommended progress payload:

```text
MediaImportProgress
├── stage
├── downloaded_bytes
├── total_bytes | None
├── speed_bytes_per_sec | None
├── eta_seconds | None
└── percent | None
```

`total_bytes=None` and `percent=None` are valid for chunked/unknown-length sources.

Cancellation is not an error.

---

# 20. Media Import Worker Boundary

New worker:

```text
workers/media_import_worker.py
```

Responsibilities:

- execute `MediaImportService` outside the Qt UI thread;
- bridge progress/status/cancel/finished/error signals;
- never mutate Project, Queue, Workspace, VideoPlayer, or artifacts.

MainWindow remains the orchestration layer that handles `MediaImportResult`.

---

# 21. URL Adapter Selection Policy

Supported strategies:

1. `DirectHTTPAdapter`
2. `YtDlpAdapter`

Routing policy:

```text
URL
→ classify

obvious direct media?
├─ yes
│  → DirectHTTPAdapter
│  → if genuine HTTP/network/media failure: STOP
│  → if response is actually non-media/page: yt-dlp may be attempted
│
└─ no
   → YtDlpAdapter
   → if UnsupportedURL / no extractor: DirectHTTP fallback allowed
   → auth/network/geo/DRM/etc.: propagate original error
```

DirectHTTP must **not** become a blind fallback for all yt-dlp failures.

Possible direct-media hints include:

```text
.mp4
.webm
.mov
.mkv
.m4v
Content-Type: video/*
```

These are routing hints only, not final trust.

---

# 22. DirectHTTPAdapter

Sprint 12 uses synchronous streaming via `requests` inside the media worker thread rather than adding an asyncio runtime.

Conceptual implementation:

```python
with session.get(url, stream=True, timeout=...) as response:
    for chunk in response.iter_content(chunk_size=...):
        cancellation_token.throw_if_cancelled()
        write(chunk)
        report_progress(...)
```

Requirements:

- streaming writes; never buffer full media in RAM;
- finite connect/read timeouts;
- finite redirect count;
- TLS certificate verification enabled;
- cancellation checked during streaming;
- proper file/socket close before cleanup;
- HTTP error mapping into the domain error taxonomy.

---

# 23. YtDlpAdapter

Sprint 12 integrates **yt-dlp through its Python API**, not shell CLI concatenation.

```text
yt_dlp.YoutubeDL(options)
```

Required policy:

```text
noplaylist = True
single video only
no cookies
no browser cookie extraction
no credentials
no custom downloader executable
no arbitrary output template from user
no arbitrary postprocessor command
```

Recommended format policy:

```text
bestvideo*+bestaudio/best
```

FFmpeg may be used by yt-dlp to merge streams.

Sprint 12 does not require transcoding every source into MP4.

---

# 24. Project-Owned Media Storage

For URL-created Projects, canonical downloaded media lives inside the intended Project bundle:

```text
<Project>.ai-subtitle/
├── project.json
├── state.json
├── workspace.json
├── media/
│   └── source.<validated-ext>
└── artifacts/
```

Import staging:

```text
<Project>.ai-subtitle/
└── media/
    └── .staging/
        └── <download-id>/
            ├── *.partial
            ├── *.part
            └── adapter fragments/temp files
```

Only app-controlled finalization creates:

```text
media/source.<ext>
```

---

# 25. Precomputed Bundle Path Rule

For **New Project from URL**, the application must not create a canonical Project before download success.

Flow:

```text
user chooses project root + name
→ derive intended bundle path
→ create staging directory only
→ download
→ validate
→ atomic finalize media
→ ProjectService.create_project(...)
→ recovery session
→ player/workspace
```

On failure/cancel:

```text
remove staging session
remove empty staging/media/bundle directories where safe
```

There must be no:

```text
project.json
state.json
artifact manifest
active recovery session
```

from a failed URL import.

---

# 26. Atomic Finalization

The application's atomic durability boundary is independent of adapter-specific temporary formats.

```text
adapter completes staged media
→ MediaProbe validates staged media
→ determine safe canonical extension
→ os.replace(staged_completed_media, media/source.ext)
→ fsync parent directory where practical/supported
→ emit MediaImportResult
```

If `os.replace` fails:

- no Project is created;
- canonical target is not considered valid;
- staging is cleaned or left only according to safe failure-cleanup policy;
- error is surfaced as `FINALIZE_FAILED`.

---

# 27. Media Validation Gate

Before canonical finalize, `MediaProbe` must verify at minimum:

```text
file exists
size > 0
ffprobe succeeds
has video stream
duration > 0
```

Optional extracted metadata:

```text
duration
resolution
codec
container
fps
```

Neither file extension nor HTTP Content-Type is the final trust boundary.

A downloaded audio-only result fails with `NO_VIDEO_STREAM`.

---

# 28. New Project Import Workflow

Exact application flow:

```text
Import Video from URL
→ validate URL
→ precompute bundle/media staging path
→ MediaImportWorker.start()
→ MediaImportService.import_url()
→ RESOLVING
→ DOWNLOADING
→ VALIDATING
→ FINALIZING
→ MediaImportResult(local_path)
→ ProjectService.create_project(bundle, name, local_path)
→ create/switch Recovery session
→ existing metadata loader
→ existing VideoPlayer
→ existing Workspace
→ Timing Draft available
→ Full Subtitle available
```

No URL-specific Project variant exists.

---

# 29. Add-to-Queue Import Workflow

Exact flow:

```text
Import Video from URL
→ choose Add to Queue
→ choose/derive safe local target storage
→ MediaImportWorker
→ MediaImportResult(local_path)
→ QueueManager.add_video(local_path)
→ existing queue metadata/player workflow
```

`QueueManager` contract remains local-path-only.

The implementation plan must choose a durable app-controlled location for URL-downloaded queue-only files that does not pretend they belong to an existing Project. This location must still use staging + atomic finalize and must not be `%TEMP%` if queue persistence/session lifetime requires the file to survive normal temp cleanup.

---

# 30. URL Import UI

Entry points may include both:

```text
File
└── Import
    ├── Video File...
    └── Video from URL...
```

and Queue actions:

```text
[ + Video ] [ URL ]
```

Both URL entry points use one dialog implementation:

```text
ui/dialogs/media_import_dialog.py
```

No duplicate import workflow is permitted.

---

# 31. Media Import Dialog State Machine

Required states:

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
any running stage → FAILED
```

Cancellation:

```text
running stage → CANCELLING → CANCELLED
```

While running:

- Import cannot be started again;
- Cancel remains available where safely cooperative;
- closing the dialog triggers cancellation/cleanup rather than abandoning a live worker.

Unknown download size uses an indeterminate progress bar plus downloaded byte count where available.

---

# 32. Context + Import UI Module Boundaries

Recommended new UI files:

```text
ui/
├── components/
│   └── transcription_context_panel.py
├── dialogs/
│   └── media_import_dialog.py
├── subtitle_generation_panel.py       # context status only
└── Gui.py                             # orchestration only
```

`Gui.py` may:

```text
open dialog
start worker
receive MediaImportResult
invoke ProjectService / QueueManager
switch active workspace
```

`Gui.py` may not own:

```text
HTTP requests
yt-dlp options
ffprobe invocation
staging mechanics
prompt truncation/token algorithms
```

---

# 33. Proposed Directory Structure

```text
core/
├── project/
│   ├── project.py                         MODIFY
│   ├── project_state.py                   existing
│   └── transcription_context.py           NEW
│
├── transcription/
│   ├── __init__.py                        NEW
│   ├── prompt_context_builder.py          NEW
│   └── token_counter.py                   NEW
│
├── media_import/
│   ├── __init__.py                        NEW
│   ├── media_import_service.py            NEW
│   ├── media_import_models.py             NEW
│   ├── media_import_errors.py             NEW
│   ├── media_probe.py                     NEW
│   ├── url_classifier.py                  NEW
│   └── adapters/
│       ├── __init__.py                    NEW
│       ├── downloader_adapter.py           NEW
│       ├── yt_dlp_adapter.py               NEW
│       └── direct_http_adapter.py          NEW
│
├── subtitle_generation/
│   ├── subtitle_generation_request.py      MODIFY
│   ├── faster_whisper_service.py           MODIFY
│   └── checkpoint-related serialization    MODIFY as required
│
└── recovery/
    ├── recovery_models.py                  MODIFY
    ├── recovery_validator.py               MODIFY
    └── recovery_manager.py                 minimal integration only

ui/
├── components/
│   └── transcription_context_panel.py      NEW
├── dialogs/
│   └── media_import_dialog.py              NEW
├── subtitle_generation_panel.py            MODIFY
└── Gui.py                                  orchestration changes only

workers/
└── media_import_worker.py                  NEW

tests/
├── test_transcription_context.py           NEW
├── test_prompt_context_builder.py          NEW
├── test_contextual_whisper.py              NEW
├── test_media_import_service.py            NEW
├── test_media_import_adapters.py           NEW
├── test_media_import_ui.py                 NEW
└── test_sprint12_end_to_end.py              NEW
```

---

# 34. Error Taxonomy

Recommended domain error codes:

```text
INVALID_URL
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

Errors are mapped to user-friendly UI messages while technical diagnostics stay in logs.

Cancellation is not displayed as an error dialog.

---

# 35. Security — Protocol & Redirects

Input accepts only HTTP(S).

DirectHTTP requirements:

- TLS verification ON;
- finite redirects;
- every redirect target revalidated as allowed network scheme;
- finite connection/read timeouts;
- no silent fallback to insecure certificate behavior.

No local filesystem/custom protocol URL is passed into download adapters.

---

# 36. Security — Path Confinement

Never trust remote metadata as a filesystem path:

```text
video title
URL basename
Content-Disposition filename
yt-dlp extractor title
```

Canonical target is app-generated, e.g.:

```text
source.mp4
source.webm
source.mkv
```

or a sanitized app-generated name.

Before any write/finalize:

```text
resolved target path MUST be descendant of target_media_dir
```

Any confinement violation is treated as a security failure.

---

# 37. Security — Shell Execution

FFmpeg/ffprobe invocation uses argument arrays and `shell=False`.

Forbidden:

```python
subprocess.run(f"ffprobe {user_input}", shell=True)
```

Required conceptual form:

```python
subprocess.run([
    ffprobe_path,
    "-v", "error",
    ...,
    staged_media_path,
], shell=False)
```

The original URL is never interpolated into a shell command.

---

# 38. Security — yt-dlp Capability Boundary

Sprint 12 must not enable:

- user-supplied arbitrary yt-dlp CLI switches;
- custom external downloader executable;
- custom postprocessor shell commands;
- arbitrary output templates supplied by users;
- automatic browser-cookie extraction;
- credential harvesting/storage;
- DRM bypass behavior.

Authentication/private/DRM-protected sources return an explicit unsupported/auth/protected error.

---

# 39. Security — Logs & Sensitive URLs

Logs may contain:

```text
adapter name
stage
URL hostname/path in redacted form
HTTP status
exception type
```

Logs must not contain:

```text
cookies
Authorization headers
credentials
full signed/auth URL query strings
browser session data
```

Default logging should redact query and fragment components from external URLs unless an explicitly safe diagnostic whitelist is later introduced.

---

# 40. Resource Protection

Downloads are streamed to disk.

No complete media file is loaded into memory.

When `Content-Length`/estimated size is available, the importer may preflight available disk space.

Runtime write failures such as `ENOSPC` map to `DISK_FULL` and trigger staging cleanup.

Sprint 12 does not impose an arbitrary fixed maximum media size.

---

# 41. Cancellation Semantics

Cancellation is cooperative:

```text
UI Cancel
→ worker cancellation token/flag
→ adapter observes cancellation
→ stop network/yt-dlp operation safely
→ close handles/process resources
→ delete staging session
→ emit cancelled
```

No Project, Queue, Player, Recovery, or Artifact mutation occurs as a result of cancellation.

---

# 42. Acceptance Tests — Contextual Transcription

## TC107 — Project v1 migration

```text
load Project v1
→ empty TranscriptionContext in RAM
→ no canonical file rewrite
```

## TC108 — Project v2 round-trip

```text
save/open Project v2
→ context + glossary preserved exactly after normalization rules
```

## TC109 — Glossary priority

```text
prompt exceeds budget
→ Context truncates before accepted glossary items
```

## TC110 — Glossary over budget

```text
glossary alone exceeds budget
→ deterministic first-N retention
→ no partial glossary item
```

## TC111 — Empty context

```text
Context + Glossary empty
→ prompt_context == ""
→ FasterWhisper receives no effective initial prompt
```

## TC112 — Context passed to Whisper

```text
Context/Glossary present
→ exact compiled request.prompt_context
→ exact initial_prompt forwarded to FasterWhisper
```

## TC113 — Resume uses immutable original prompt

```text
start generation with P
→ checkpoint
→ edit Project Context to P2
→ resume
→ still uses P
```

## TC114 — Context edit participates in revision/recovery

```text
edit context/glossary
→ one logical external revision transition
→ dirty true
→ recovery snapshot includes unsaved context
```

## TC115 — Crash restore preserves context

```text
unsaved context edit
→ durable recovery snapshot
→ crash/restore
→ context + glossary restored
→ dirty until explicit Save
```

---

# 43. Acceptance Tests — Media Import

## TC116 — Direct MP4 import

```text
direct media URL
→ DirectHTTPAdapter
→ validated atomic local file
```

## TC117 — Supported website import

```text
supported webpage URL
→ YtDlpAdapter
→ validated atomic local media
```

## TC118 — Unsupported extractor fallback

```text
yt-dlp UnsupportedURL/no extractor
→ DirectHTTP fallback allowed
```

## TC119 — No masking of real yt-dlp failures

```text
yt-dlp auth/network/DRM/etc. error
→ original classified failure
→ no blind DirectHTTP fallback
```

## TC120 — Cancel mid-download

```text
cancel during download
→ worker/service cancellation
→ staging removed
→ no Project created
```

## TC121 — Network failure cleanup

```text
network failure
→ staging removed
→ canonical target absent
→ no Project mutation
```

## TC122 — Invalid media payload

```text
download completes
→ ffprobe/media validation fails
→ no canonical Project
```

## TC123 — Atomic finalize failure

```text
os.replace fails
→ no canonical media accepted
→ no Project mutation
```

## TC124 — Successful URL import creates canonical SourceInfo

```text
URL import succeeds
→ Project.source.path == finalized local media
→ source fingerprint generated from local media
```

## TC125 — Player reuse

```text
successful import
→ existing VideoPlayer receives finalized local path
```

## TC126 — Timing Draft reuse

```text
successful import
→ existing Timing Draft operates on same Project.source.path
```

## TC127 — Full Subtitle reuse

```text
successful import
→ SubtitleGenerationRequest.video_path == Project.source.path
```

## TC128 — Source guard survives reopen

```text
URL import
→ save/close/reopen Project
→ source path/fingerprint guard remains valid
```

## TC129 — Full Sprint 12 URL E2E

```text
URL
→ adapter
→ staging
→ validation
→ atomic finalize
→ create Project
→ VideoPlayer
→ Timing Draft
→ Full Subtitle
→ Save
→ close
→ reopen
→ same valid source fingerprint
```

CI must use injectable fakes/mocks for network adapters and media probes where appropriate. Internet availability is not required for acceptance tests.

---

# 44. Regression Gates

Sprint 12 must not regress:

- Sprint 9 robust generation/checkpoint behavior.
- Sprint 10 canonical segment schema/editing/undo behavior.
- Sprint 11 dirty state, recovery snapshot, source mismatch guard, handoff, close matrix, single-instance IPC, explicit Save semantics, and Export != Save semantics.

Required final verification remains:

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
```

CI workflow only changes if existing test discovery/dependencies cannot discover the new test modules or required runtime dependency installation.

---

# 45. Dependencies

Expected new Python dependencies:

```text
yt-dlp
requests
```

If `requests` is already transitively available, it must still be declared explicitly if production code imports it directly.

FFmpeg/ffprobe remain runtime dependencies through existing runtime-path/tooling conventions.

No asyncio-specific HTTP dependency is added in Sprint 12.

---

# 46. Implementation Boundaries Summary

```text
TranscriptionContext
→ user-owned domain metadata

PromptContextBuilder
→ deterministic derived prompt compiler

SubtitleGenerationRequest
→ immutable generation transaction snapshot

FasterWhisperService
→ ASR adapter; consumes initial_prompt only

MediaImportDialog
→ presentation/state display

MediaImportWorker
→ background execution bridge

MediaImportService
→ URL-to-local-media transaction

URLClassifier
→ adapter routing

YtDlpAdapter / DirectHTTPAdapter
→ download mechanics

MediaProbe
→ media trust/validation boundary

MainWindow
→ application orchestration only

ProjectService
→ canonical Project lifecycle

QueueManager
→ queue lifecycle

RecoveryManager / RevisionTracker
→ unchanged ownership of durability/dirty truth, extended to cover transcription context
```

---

# 47. Design Rulings Locked for Sprint 12

1. **Contextual Whisper uses Option A only:** `initial_prompt`; no Local LLM.
2. **Project stores Context + Glossary, never compiled prompt.**
3. **Default prompt budget is runtime policy (180), not persisted schema.**
4. **Glossary has priority over Context.**
5. **Generation resume preserves original compiled prompt.**
6. **URL import is download-first/local-file-first.**
7. **MediaImportService is isolated from Project/Queue/Player/Whisper.**
8. **yt-dlp + Direct HTTP are hidden behind adapters.**
9. **DirectHTTP is not a blind fallback for every yt-dlp error.**
10. **Project media is validated with ffprobe before canonical acceptance.**
11. **URL import never replaces an existing Project source.**
12. **New Project is created only after successful media finalization.**
13. **Failed/cancelled imports create zero canonical Project side effects.**
14. **MainWindow remains orchestration-only; downloader/prompt internals stay outside `Gui.py`.**
15. **Only HTTP(S) external URLs are supported.**
16. **No cookies, browser credentials, DRM bypass, arbitrary shell hooks, or arbitrary yt-dlp arguments.**
17. **Path confinement and shell-free subprocess execution are mandatory.**
18. **Context/Glossary edits participate in RevisionTracker and Recovery.**
19. **Timing Draft does not consume Context.**
20. **Existing local Project/Player/Timing/Full Subtitle pipeline is reused after URL finalization.**

---

# 48. Definition of Done

Sprint 12 is complete when all of the following are true:

### Contextual Transcription

```text
✅ Project v2 persists Context + Glossary
✅ Project v1 opens with backward-compatible defaults
✅ Context/Glossary edits are revision tracked
✅ Recovery protects unsaved Context/Glossary
✅ Prompt compilation is deterministic and bounded
✅ Glossary priority is enforced
✅ Faster-Whisper receives initial_prompt
✅ Empty context produces no effective prompt
✅ Checkpoint/resume keeps the original prompt transaction
```

### Media Import

```text
✅ URL dialog supports New Project / Add to Queue
✅ yt-dlp adapter works through Python API
✅ Direct HTTP adapter streams downloads
✅ adapter routing/fallback policy is classified
✅ progress + cancellation are non-blocking
✅ staging is isolated
✅ media is ffprobe validated
✅ atomic finalization is app-controlled
✅ failed/cancelled import leaves zero Project side effects
✅ successful import creates a local source fingerprint
✅ existing VideoPlayer is reused
✅ existing Timing Draft is reused
✅ existing Full Subtitle is reused
✅ source guard works after save/reopen
```

### Security / Architecture

```text
✅ HTTP(S)-only URL boundary
✅ TLS verification enabled
✅ path traversal prevented
✅ shell=False subprocess usage
✅ no credential/cookie/DRM bypass surface
✅ sensitive URL query data redacted from logs
✅ MediaImportService has no Project/UI/Whisper dependencies
✅ MainWindow remains orchestration-only
```

### Verification

```text
✅ TC107–TC129 pass
✅ full regression suite passes
✅ compileall passes
✅ worktree clean
✅ PR review finds no unresolved Critical/Important issues
```
