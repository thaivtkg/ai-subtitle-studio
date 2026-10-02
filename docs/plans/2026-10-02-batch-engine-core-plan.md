# Batch Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data foundation and core orchestrator for the Phase 3A Batch Engine without touching the current UI.

**Architecture:** A robust background orchestration system consisting of declarative data models (`BatchJob`, `BatchSession`), an orchestrator (`BatchManager`), integration with services, and state serialization for crash recovery.

**Tech Stack:** Python 3.11, PySide6 (Signals/Slots, QObject, QRunnable), JSON.

**Spec:** `docs/specs/2026-10-02-batch-engine-design.md`

## Global Constraints
- Do not import UI components into Core.
- Strict Core Freeze on existing logic unless explicitly bridging to BatchManager.

## Review Focus
- Serialization errors (e.g. invalid JSON types) when writing to `batch_active.json`.
- QThread/QRunnable signal crossing: ensuring signals emit safely from background to main thread.
- Error propagation during the pipeline (Whisper/FFmpeg failures) should not crash the orchestrator.

---

### Task 1: Data Models & Enums

**Files:**
- Create: `core/batch/batch_models.py`
- Test: `tests/test_batch_models.py`

**Interfaces:**
- Produces: `BatchStatus` (Enum), `BatchJob` (dataclass), `BatchSession` (dataclass) with `to_dict()` / `from_dict()` methods.

- [ ] **Step 1: Write the failing test**
Write a test to verify initialization and serialization/deserialization of `BatchJob` and `BatchSession` using standard library `json` and `dataclasses.asdict`.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_batch_models.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement Data Models in `core/batch/batch_models.py`**
Use `dataclass` and `Enum`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_batch_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
Run:
`git add tests/test_batch_models.py core/batch/batch_models.py`
`git commit -m "feat(batch): implement batch data models"`

---

### Task 2: Batch Orchestrator & Signals

**Files:**
- Create: `core/batch/batch_manager.py`
- Test: `tests/test_batch_manager.py`

**Interfaces:**
- Consumes: `BatchJob`, `BatchSession`, `BatchStatus`
- Produces: `BatchManager(QObject)` with `session_started`, `job_status_changed(str, BatchStatus)`, `job_progress_updated(str, int)`, `session_completed` signals.

- [ ] **Step 1: Write the failing test**
Test that `BatchManager` can be instantiated, can receive a `BatchSession` via `start_session(session)`, and emits dummy signals appropriately. 

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_batch_manager.py -v`

- [ ] **Step 3: Implement Orchestrator scaffolding**
Implement `BatchManager(QObject)` with signal declarations and a basic queue setup (e.g., using `QThreadPool` and `QRunnable` or a simple worker).

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_batch_manager.py -v`

- [ ] **Step 5: Commit**
Commit changes.

---

### Task 3: Pipeline Integration (The Execution Loop)

**Files:**
- Modify: `core/batch/batch_manager.py`
- Test: `tests/test_batch_pipeline.py`

**Interfaces:**
- Consumes: `MediaImportService`, `FasterWhisperService`, `ExportService` (mocked in tests).

- [ ] **Step 1: Write the failing test**
Mock the three services. Queue two jobs where one throws an Exception during translation. Assert that the manager catches it, sets `FAILED` for job 1, and successfully completes job 2.

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement Execution Loop**
In `BatchManager` worker logic, iterate over jobs: MediaImport -> Whisper -> Export. Wrap each in try/except. Update signals accordingly.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

---

### Task 4: Recovery & Persistence Integration

**Files:**
- Modify: `core/batch/batch_manager.py`
- Modify: `core/runtime/runtime_paths.py` (Add `get_batch_active_file()`)
- Modify: `core/recovery/recovery_manager.py`
- Test: `tests/test_batch_recovery.py`

**Interfaces:**
- Consumes: `BatchSession.to_dict()`

- [ ] **Step 1: Write the failing test**
Test that after a `job_status_changed`, `batch_active.json` is overwritten. Test that `RecoveryManager` detects `batch_active.json` on startup.

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement Persistence**
Hook signal to write file. Add detection logic in `RecoveryManager`.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**
