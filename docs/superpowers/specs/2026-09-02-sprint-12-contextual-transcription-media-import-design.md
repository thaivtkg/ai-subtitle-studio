# Sprint 12 — Contextual Transcription & Media Import

**Status:** Locked Design Spec — pending final user review  
**Date:** 2026-09-02  
**Target branch:** `sprint-12`  
**Base:** `master` after Sprint 11 (`4f827b32c1d5df5ba6980dd6c66af5e92c687825`)  

## 1. Goal

Sprint 12 restores and strengthens contextual transcription while adding secure URL-based video import without creating a second media-processing pipeline.

Two coordinated capabilities are introduced:

1. **Contextual Transcription** — Project-owned Context + Glossary is compiled deterministically into a bounded Whisper `initial_prompt` for each new generation transaction.
2. **Media Import from URL** — external URLs are resolved/downloaded into validated local media first; only then are existing Project, Queue, VideoPlayer, Timing Draft, Full Subtitle, Recovery, and Artifact workflows reused.

Core rules:

> Audio remains the source of truth. Context only biases transcription.

> URLs are import sources, never canonical media identities. Canonical media is always a validated local file.

> Failed or cancelled URL import must leave zero canonical Project side effects.

---

## 2. Non-goals

Sprint 12 does **not** include:

- Local LLM post-processing or translation.
- Rewriting subtitle text according to lore/style.
- Replacing the source video of an existing Project.
- Playlist/batch playlist download.
- Livestream recording.
- DRM bypass.
- Authentication/cookies UI.
- Browser-cookie extraction or credential storage.
- Downloading remote subtitle tracks.
- Direct URL playback in VideoPlayer.
- Direct URL transcription in Whisper.
- A second URL-specific Timing/ASR pipeline.
- Arbitrary yt-dlp arguments, output templates, custom downloaders, or shell postprocessors.
- Media transcoding solely for import compatibility.
- A chip/tag-heavy glossary editor.

---

# 3. Existing Architecture Constraints

Sprint 12 extends current boundaries:

- `ProjectService` owns canonical Project lifecycle/persistence.
- `Project.source.path` + fingerprint remain canonical media identity.
- `QueueManager.add_video()` receives existing local filesystem paths.
- `SubtitleGenerationRequest.video_path` remains local-path-only.
- `FasterWhisperService` consumes local media through the existing FFmpeg batch-extraction path.
- Timing Draft and Full Subtitle reuse current project/source workflows.
- `RevisionTracker` remains dirty-state source of truth.
- `RecoveryManager` protects unsaved canonical working state.
- Workers execute; Services own domain transactions; MainWindow orchestrates application/UI flow.
- `Gui.py` must not absorb downloader, media-probe, or prompt-compilation internals.

No new subtitle domain model is introduced.

---

# 4. Locked Invariants

## 4.1 Local-media-first

```text
URL
→ resolve/download
→ staging media
→ media validation
→ atomic finalize
→ canonical local media
→ existing application pipeline
```

No production equivalents of `load_url_video()`, `generate_from_url()`, or `timing_from_url()` are allowed.

## 4.2 No source replacement

URL import may only:

- create a **New Project**, or
- create durable local media and **Add to Queue**.

It never replaces an existing Project source.

## 4.3 Zero canonical side effects before finalize

Before media finalization succeeds:

```text
ProjectService untouched
QueueManager untouched
VideoPlayer untouched
Recovery untouched
ArtifactStore untouched
```

Only staging directories/files may exist.

## 4.4 Context domain data

Project persistence stores only:

```text
context: str
glossary: list[str]
```

Compiled/model-specific prompt text is never Project metadata.

## 4.5 Derived immutable generation prompt

```text
Project.transcription_context
→ PromptContextBuilder
→ CompiledPromptContext
→ SubtitleGenerationRequest.prompt_context
```

Once a generation transaction starts, its compiled prompt is immutable and is preserved by checkpoint/resume.

## 4.6 Glossary priority

Within the configured budget:

1. accepted Glossary terms are allocated first in stable order;
2. remaining budget goes to Context;
3. Context truncates before accepted Glossary terms;
4. a Glossary item is never partially cut;
5. if Glossary alone exceeds budget, deterministic first-N retention applies.

## 4.7 Audio truth

Context is passed only as Whisper `initial_prompt`; it never becomes an LLM rewrite stage. Timing Draft is VAD-only and does not consume Context.

## 4.8 Recovery coverage

Unsaved Context/Glossary edits are canonical working-state changes and must:

- increment one logical external revision;
- mark the session dirty;
- be included in recovery snapshots;
- restore after crash;
- remain dirty after recovery until explicit Save.

## 4.9 Atomic media acceptance

```text
adapter output in staging
→ MediaProbe validates
→ app-controlled os.replace(..., canonical_path)
→ only now return MediaImportResult
```

Adapter-specific `.part`, fragments, or merge temporaries are not the application's durability contract.

## 4.10 Worker/service boundary

`MediaImportWorker` executes `MediaImportService` only. `MediaImportService` has no dependency on Project, Queue, MainWindow, VideoPlayer, Whisper, Timing, or ArtifactStore.

## 4.11 Network security boundary

Only `http://` and `https://` are accepted. URL validation must reject local/non-network schemes and must also prevent connections to loopback, link-local, private, multicast, unspecified, and other non-public address ranges unless a future explicit trusted-local-source feature is designed separately.

DNS resolution and **every redirect target** must be revalidated so a public-looking hostname cannot redirect or re-resolve into a blocked local/private address.

---

# 5. Project Schema v2

New domain model:

```python
@dataclass
class TranscriptionContext:
    context: str = ""
    glossary: list[str] = field(default_factory=list)
```

Project shape:

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

`project.json` persists `transcription_context`; `state.json` and `workspace.json` do not.

Example:

```json
{
  "schema_version": 2,
  "project_id": "uuid",
  "name": "Example",
  "source": {"path": "...", "fingerprint": "..."},
  "transcription_context": {
    "context": "Trận chiến tại Demacia...",
    "glossary": ["Demacia", "Garen", "Lux", "Petricite"]
  }
}
```

---

# 6. Project v1 → v2 Migration

Opening a v1 Project with no transcription context produces in-memory defaults:

```text
context = ""
glossary = []
```

Opening/migrating does **not** rewrite canonical files. The v2 shape is persisted only on explicit Save.

---

# 7. Glossary Normalization

Canonical normalization:

1. trim whitespace;
2. remove empty entries;
3. deduplicate by `casefold()`;
4. keep visible spelling of first occurrence;
5. preserve stable input order.

Example:

```text
Demacia
demacia
 DEMACIA
```

becomes exactly one visible entry:

```text
Demacia
```

No hidden alphabetical sort.

---

# 8. Context Edit Semantics

```text
user edits
→ 300–500 ms debounce or focus-out commit
→ Project.transcription_context updated
→ ProjectService.mark_dirty()
→ RevisionTracker.record_external_change()
→ Recovery autosave eligible
```

Continuous typing must not increment revision once per keystroke.

There is no separate Save Context button. Existing canonical Save/Ctrl+S semantics apply.

---

# 9. Recovery Schema Extension

`RecoveryWorkingState` gains:

```text
transcription_context
├── context
└── glossary[]
```

Recovery snapshots continue to contain canonical working state only; compiled prompt strings are not separately duplicated into recovery state unless they already belong to an active generation checkpoint owned by the generation subsystem.

---

# 10. PromptContextBuilder

New subsystem:

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

A token-counter dependency is injected through a small protocol:

```python
class TokenCounterProtocol(Protocol):
    def count(self, text: str) -> int: ...
```

`DEFAULT_PROMPT_BUDGET = 180` is a conservative runtime policy, not persisted Project data and not a claim that every Whisper/model version has an identical hard limit.

---

# 11. CompiledPromptContext

Recommended immutable model:

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

The UI may display diagnostics but cannot edit compiled text directly.

---

# 12. Prompt Compilation Algorithm

```text
normalize glossary
→ append terms in stable order while each complete item fits
→ reserve accepted terminology
→ append Context using remaining budget
→ truncate Context at sentence boundary if possible
→ else whitespace boundary
→ hard boundary only as last resort
→ return text + diagnostics
```

Recommended representation:

```text
Terminology: Demacia, Noxus, Garen, Lux, Petricite.
Context: Trận chiến tại Demacia. Garen đang nói chuyện với Lux.
```

If both inputs are empty, compiled text is `""`.

---

# 13. Contextual Generation Contract

`SubtitleGenerationRequest` gains:

```python
prompt_context: str = ""
```

New generation:

```text
Generate
→ read Project.transcription_context
→ compile once
→ put compiled text into request
→ generation/checkpoint owns that request snapshot
→ FasterWhisperService
→ model.transcribe(..., initial_prompt=request.prompt_context or None)
```

The request does not carry raw Context/Glossary.

---

# 14. Checkpoint / Resume Transaction

```text
start with compiled prompt P
→ checkpoint persists request containing P
→ Project context changes to P2
→ Resume old run
→ uses P
→ only a new run compiles/uses P2
```

This invariant is mandatory for deterministic batch output and debugging.

---

# 15. Context UI/UX

Context belongs to the active Project and appears in the Right Inspector:

```text
Right Inspector
├── Subtitle
├── Generate
└── Context
```

Context panel:

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

When necessary:

```text
⚠ 8/14 glossary terms included
⚠ Context truncated
```

Optional `Preview compiled prompt` is read-only.

`SubtitleGenerationPanel` only shows compact Context status and an `Edit Context` navigation action. It never duplicates the editor.

---

# 16. Media Import Architecture

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
→ ProjectService or QueueManager
```

New core structure:

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

---

# 17. MediaImportResult / Progress

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

Metadata may include duration, width, height, codec, container, and fps.

Progress stages:

```text
RESOLVING
DOWNLOADING
VALIDATING
FINALIZING
```

Progress payload:

```text
MediaImportProgress
├── stage
├── downloaded_bytes
├── total_bytes | None
├── speed_bytes_per_sec | None
├── eta_seconds | None
└── percent | None
```

Unknown total size is a valid indeterminate-progress case.

---

# 18. Adapter Selection Policy

```text
URL
→ validate public HTTP(S) target
→ classify

obvious direct media?
├─ yes
│  → DirectHTTPAdapter
│  → genuine HTTP/network/media failure: STOP
│  → response is actually page/non-media: yt-dlp may be tried
│
└─ no
   → YtDlpAdapter
   → UnsupportedURL/no extractor: DirectHTTP fallback allowed
   → auth/network/geo/DRM/etc.: propagate classified original failure
```

DirectHTTP is never a blind fallback for arbitrary yt-dlp failures.

Extension/Content-Type are routing hints, not final media trust.

---

# 19. DirectHTTPAdapter

Sprint 12 uses `requests` streaming in the worker thread rather than adding an asyncio runtime.

Requirements:

- stream chunks to disk;
- never load whole media into RAM;
- finite connect/read timeout;
- finite redirect count;
- TLS verification ON;
- URL/IP policy rechecked after DNS resolution and redirects;
- cancellation checked during streaming;
- HTTP failures mapped into the domain taxonomy;
- no Authorization/cookie injection from browser state.

---

# 20. YtDlpAdapter

Use yt-dlp **Python API**, not shell command concatenation:

```text
yt_dlp.YoutubeDL(options)
```

Locked policy:

```text
noplaylist = True
single video only
no cookies
no browser cookie extraction
no credentials
no arbitrary user output template
no custom external downloader
no arbitrary postprocessor command
```

Recommended format:

```text
bestvideo*+bestaudio/best
```

FFmpeg may merge streams. Sprint 12 does not mandate transcoding every source to MP4.

The final resolved media/network requests used by the adapter must remain subject to the same public-network security policy; redirects/resolved endpoints must not be allowed to pivot into blocked local/private destinations.

---

# 21. Media Validation Gate

Before finalization, `MediaProbe` requires:

```text
file exists
size > 0
ffprobe succeeds
has video stream
duration > 0
```

Audio-only results fail with `NO_VIDEO_STREAM`.

The final trust boundary is ffprobe/media structure, not extension or HTTP Content-Type.

---

# 22. Project-Owned Media Storage

For **New Project from URL**:

```text
<Project>.ai-subtitle/
├── project.json
├── state.json
├── workspace.json
├── media/
│   └── source.<validated-ext>
└── artifacts/
```

During import only staging exists:

```text
<Project>.ai-subtitle/media/.staging/<download-id>/...
```

Canonical Project files are not created until media has been successfully finalized.

---

# 23. Precomputed Bundle Path Rule

```text
user chooses root + Project name
→ derive intended <Project>.ai-subtitle path
→ create media/.staging/<id> only
→ download
→ validate
→ atomic media finalize
→ ProjectService.create_project(...)
→ recovery session
→ existing Player/Workspace
```

Failure/cancel removes staging and empty directories where safe. It must leave no `project.json`, `state.json`, Artifact manifest, or Recovery session.

---

# 24. Queue-Only URL Storage

To remove lifecycle ambiguity, **Add to Queue from URL uses a durable app-owned import cache**, not `%TEMP%` and not a fake Project bundle.

`RuntimePaths` gains an app-data location conceptually equivalent to:

```text
%LOCALAPPDATA%/AI Subtitle Studio/media_imports/
└── <import-id>/
    ├── .staging/
    └── source.<validated-ext>
```

Exact OS path construction remains owned by `RuntimePaths`; no media-import component hardcodes `%LOCALAPPDATA%`.

Queue-only workflow:

```text
URL
→ RuntimePaths media-import staging
→ download + validate + atomic finalize
→ QueueManager.add_video(finalized_local_path)
```

Lifecycle rule for Sprint 12:

- a successfully finalized queue-only media file remains durable for the app session and future Project creation/use;
- removing a Queue item does **not** automatically delete the underlying file in Sprint 12 because ownership may already have escaped to downstream workflows;
- automatic cache garbage collection is a non-goal for Sprint 12 and may be designed later.

This intentionally prefers data safety over aggressive disk cleanup.

---

# 25. Atomic Finalization

For Project media and queue-only media alike:

```text
adapter completes staged media
→ MediaProbe validates
→ choose app-controlled canonical filename/extension
→ os.replace(staged_completed_media, canonical_path)
→ fsync parent directory where supported/practical
→ return MediaImportResult
```

If `os.replace` fails, no canonical media is accepted and no downstream Project/Queue mutation occurs.

---

# 26. New Project Import Workflow

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

No URL-specific Project type exists.

---

# 27. Add-to-Queue Workflow

```text
Import Video from URL
→ choose Add to Queue
→ RuntimePaths media_imports/<id> staging
→ MediaImportWorker
→ MediaImportResult(local_path)
→ QueueManager.add_video(local_path)
→ existing Queue metadata/player workflow
```

`QueueManager` remains local-path-only.

---

# 28. URL Import UI

Shared dialog:

```text
ui/dialogs/media_import_dialog.py
```

Entry points may include:

```text
File > Import > Video from URL...
Queue > URL
```

Both open the same implementation.

Initial state:

```text
URL [................................]
Import as:
● New Project
○ Add to Queue

Project Location [Browse...]   # New Project only
Project Name     [...]         # New Project only

[Cancel] [Import]
```

Running states:

```text
RESOLVING → DOWNLOADING → VALIDATING → FINALIZING → SUCCEEDED
```

Failure goes to `FAILED`; cancel goes through `CANCELLING → CANCELLED`.

Closing a running dialog triggers cooperative cancellation/cleanup instead of abandoning a worker.

---

# 29. MainWindow / Module Boundaries

New UI/worker files:

```text
ui/components/transcription_context_panel.py
ui/dialogs/media_import_dialog.py
workers/media_import_worker.py
```

MainWindow may:

```text
open dialog
start worker
receive result
call ProjectService / QueueManager
switch active workspace
```

MainWindow may not own:

```text
HTTP requests
yt-dlp configuration
ffprobe invocation
staging mechanics
prompt token/truncation internals
```

This is a targeted responsibility cleanup, not a broad unrelated refactor.

---

# 30. Security — URL, DNS, Redirects, SSRF

Accepted schemes:

```text
http
https
```

Rejected before adapters:

```text
file
ftp
smb
data
javascript
custom schemes
```

For HTTP(S), the importer must reject targets resolving to blocked address classes, including at minimum:

```text
loopback
private RFC1918 / equivalent IPv6 private ranges
link-local
unspecified
multicast
reserved/non-public ranges where appropriate
```

Requirements:

1. resolve hostname before connection where the adapter permits;
2. validate all resolved candidate addresses;
3. validate every redirect destination;
4. protect against DNS rebinding/time-of-check-time-of-use by validating the actual connected/resolved target as close to connection time as the HTTP/adapter API allows;
5. never weaken TLS verification.

This rule applies conceptually to both DirectHTTP and yt-dlp-mediated network access.

---

# 31. Security — Path Confinement

Never trust remote title, URL basename, Content-Disposition, or extractor title as a filesystem path.

Canonical filenames are app-controlled, e.g.:

```text
source.mp4
source.webm
source.mkv
```

Before write/finalize:

```text
resolved output path MUST be a descendant of the configured target directory
```

Any traversal/confinement violation is a security failure.

---

# 32. Security — Shell Execution

FFmpeg/ffprobe use argument arrays and `shell=False`.

Forbidden:

```python
subprocess.run(f"ffprobe {user_input}", shell=True)
```

The URL is never interpolated into shell commands.

---

# 33. Security — Logs

Logs may contain adapter, stage, redacted hostname/path, HTTP status, and exception type.

Logs must not contain cookies, Authorization headers, credentials, browser session data, or full signed/auth query strings.

Default URL logging removes query and fragment components.

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

`UNSAFE_URL` covers blocked schemes, private/local address targets, unsafe redirects, and related network-boundary violations.

Cancellation is not shown as an error dialog.

---

# 35. Resource Protection / Cancellation

Downloads stream to disk; no whole-media buffering.

If expected size is known, available disk space may be preflighted. Runtime `ENOSPC` maps to `DISK_FULL`.

No arbitrary fixed video-size cap is imposed in Sprint 12.

Cancellation:

```text
UI Cancel
→ worker cancellation token
→ adapter stops cooperatively
→ close handles/resources
→ delete staging session
→ emit cancelled
```

No downstream canonical mutation occurs.

---

# 36. Proposed Directory Structure

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
│   ├── media_probe.py                     NEW
│   ├── url_classifier.py                  NEW
│   └── adapters/
│       ├── __init__.py                    NEW
│       ├── downloader_adapter.py           NEW
│       ├── yt_dlp_adapter.py               NEW
│       └── direct_http_adapter.py          NEW
├── runtime/
│   └── runtime_paths.py                    MODIFY for queue-only import cache
├── subtitle_generation/
│   ├── subtitle_generation_request.py      MODIFY
│   ├── faster_whisper_service.py           MODIFY
│   └── checkpoint serialization            MODIFY as required
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

# 37. Acceptance Tests — Contextual Transcription

**TC107 — Project v1 migration**  
Load v1 → empty `TranscriptionContext` in RAM → no canonical rewrite.

**TC108 — Project v2 round-trip**  
Save/open v2 → Context preserved; Glossary preserved in its canonical normalized form and stable order.

**TC109 — Glossary priority**  
Budget exceeded → Context truncates before accepted Glossary terms.

**TC110 — Glossary over budget**  
First-N deterministic retention; no partial term.

**TC111 — Empty context**  
Compiled prompt empty → no effective Whisper initial prompt.

**TC112 — Context passed to Whisper**  
Exact compiled `request.prompt_context` reaches `initial_prompt`.

**TC113 — Immutable resume prompt**  
Start P → checkpoint → Project changes to P2 → resume still uses P.

**TC114 — Revision/recovery participation**  
Logical Context/Glossary commit → one revision transition → dirty → recovery snapshot contains edit.

**TC115 — Crash restore**  
Unsaved Context/Glossary survives recovery and remains dirty until explicit Save.

---

# 38. Acceptance Tests — Media Import

**TC116 — Direct media**  
Direct MP4/compatible URL → DirectHTTP → validated atomic local file.

**TC117 — Supported webpage**  
Supported site URL → yt-dlp → validated atomic local media.

**TC118 — Unsupported extractor fallback**  
yt-dlp UnsupportedURL/no extractor → DirectHTTP fallback allowed.

**TC119 — No masked real failure**  
Auth/network/DRM/geo failure → classified original error → no blind fallback.

**TC120 — Cancel**  
Cancel mid-download → staging removed → no Project/Queue mutation.

**TC121 — Network failure**  
Failure → staging removed → canonical target absent.

**TC122 — Invalid media**  
Download completes → ffprobe invalid/no video → no downstream mutation.

**TC123 — Finalize failure**  
`os.replace` failure → no canonical media accepted → no Project/Queue mutation.

**TC124 — New Project SourceInfo**  
Successful import → Project source points to finalized local media → fingerprint generated locally.

**TC125 — Player reuse**  
Existing VideoPlayer receives same finalized local path.

**TC126 — Timing reuse**  
Existing Timing Draft operates on `Project.source.path`.

**TC127 — Full Subtitle reuse**  
Generation request `video_path == Project.source.path`.

**TC128 — Reopen source guard**  
Save/close/reopen → same valid local source fingerprint.

**TC129 — Full URL E2E**  
URL → adapter → staging → validate → finalize → Project → Player → Timing Draft → Full Subtitle → Save → reopen → valid source guard.

**TC130 — Queue-only durable storage**  
URL → app-owned `media_imports/<id>` → atomic finalize → Queue receives local path → no fake Project created.

**TC131 — SSRF/redirect guard**  
Loopback/private/link-local target or redirect is rejected as `UNSAFE_URL` before canonical download acceptance.

CI uses injectable fake adapters/resolvers/probes; Internet access is not required.

---

# 39. Regression Gates

Must not regress:

- Sprint 9 generation/checkpoint behavior.
- Sprint 10 canonical segments/editing/undo.
- Sprint 11 Recovery, source guard, handoff, dirty semantics, single-instance IPC, explicit Save, and Export != Save.

Final verification:

```bash
python -m unittest discover -s tests -v
python -m compileall core ui workers tests main.py
```

CI changes only if current discovery/dependency installation cannot cover Sprint 12.

---

# 40. Dependencies

Production direct dependencies added explicitly if not already direct:

```text
yt-dlp
requests
```

FFmpeg/ffprobe continue through existing runtime-path/tooling conventions.

No asyncio HTTP dependency is added.

---

# 41. Locked Design Rulings

1. Contextual Whisper = `initial_prompt` only; no Local LLM.
2. Project persists Context + Glossary, never compiled prompt.
3. Prompt budget is runtime policy; default 180.
4. Glossary priority over Context.
5. Resume preserves original compiled prompt.
6. URL import is download-first/local-file-first.
7. MediaImportService is isolated from Project/UI/Whisper/Timing.
8. yt-dlp + Direct HTTP live behind adapters.
9. DirectHTTP is not a blind fallback.
10. ffprobe validation is mandatory before canonical acceptance.
11. URL import never replaces an existing Project source.
12. New Project is created only after media finalize succeeds.
13. Failed/cancelled import creates zero canonical Project/Queue side effects.
14. Queue-only media uses durable app-owned `RuntimePaths` storage, not `%TEMP%` and not a Project bundle.
15. MainWindow remains orchestration-only.
16. Only public HTTP(S) destinations are supported; private/local SSRF targets and unsafe redirects are rejected.
17. TLS verification, path confinement, shell-free subprocess execution, and log redaction are mandatory.
18. No cookies, credentials, browser-cookie extraction, DRM bypass, or arbitrary yt-dlp/shell hooks.
19. Context/Glossary participates in RevisionTracker + Recovery.
20. Timing Draft does not consume Context.
21. Existing local Player/Timing/Full Subtitle pipelines are reused after finalization.
22. Automatic cleanup/garbage collection of successfully imported queue-only media is deferred to a future design to avoid accidental data loss.

---

# 42. Definition of Done

### Contextual Transcription

```text
✅ Project v2 persistence
✅ v1 backward-compatible load
✅ revision tracking
✅ recovery coverage
✅ deterministic bounded prompt
✅ glossary priority
✅ Whisper initial_prompt wiring
✅ immutable checkpoint/resume prompt
```

### Media Import

```text
✅ shared URL import dialog
✅ New Project + Add to Queue
✅ yt-dlp Python adapter
✅ Direct HTTP streaming adapter
✅ progress/cancel
✅ classified fallback policy
✅ public-network/SSRF guard
✅ isolated staging
✅ ffprobe validation
✅ atomic finalize
✅ Project-owned media for New Project
✅ RuntimePaths-owned durable media for Queue-only import
✅ existing Player/Timing/Full Subtitle reuse
✅ valid source fingerprint after reopen
```

### Security / Architecture

```text
✅ HTTP(S)-only + public destination validation
✅ DNS/redirect revalidation
✅ TLS verification ON
✅ path traversal prevention
✅ shell=False
✅ no auth/cookie/DRM bypass surface
✅ sensitive URL redaction
✅ service boundaries preserved
✅ MainWindow orchestration-only
```

### Verification

```text
✅ TC107–TC131 pass
✅ full regression suite passes
✅ compileall passes
✅ worktree clean
✅ PR review has no unresolved Critical/Important findings
```
