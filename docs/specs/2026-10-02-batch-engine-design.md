# Batch Engine (Phase 3A) Design Specification

## 1. Overview
The Batch Engine allows AI Subtitle Studio to process multiple media files sequentially or in parallel without human intervention. It serves as the automation foundation for Phase 3, encompassing queue management, progress tracking, and resilient error recovery.

## 2. Data Models
- **BatchJob (File-level):** Represents a single media file.
  - States: PENDING, EXTRACTING, TRANSLATING, EXPORTING, COMPLETED, FAILED.
  - Properties: Source file path, individual progress percentage, error logs.
- **BatchSession (Session-level):** Represents the entire batch run.
  - Contains: List of BatchJob objects.
  - Configuration: Target Language, Whisper Model size, Output Formats.
  - Serialization: Continuously saved to disk as JSON for crash recovery.

## 3. Core Managers
- **BatchManager (Core Worker):**
  - Consumes BatchSession and queues the BatchJobs.
  - Coordinates existing services (MediaImportService, FasterWhisperService, ExportService).
  - Emits Qt Signals: job_progress_updated, job_status_changed, atch_completed.
  - Error Handling: A FAILED job does not halt the session; it skips to the next job.
- **RecoveryManager / AutosaveCoordinator Integration:**
  - Persists the active session to atch_active.json.
  - On startup, intercepts the launch sequence if an unfinished batch is detected, prompting the user to resume.

## 4. Data Flow (UX to Core)
1. **Input:** User drops >1 files into the Start Screen -> System opens BatchSetupDialog.
2. **Setup:** User configures global model/language -> Submits to BatchManager.start_session().
3. **Transition:** UI switches to BatchProgressDashboard.
4. **Execution Loop:**
   - Pop BatchJob.
   - EXTRACTING (Audio separation).
   - TRANSLATING (Whisper STT with stdout progress parsing).
   - EXPORTING (Generate .srt / .ass).
   - Update job to COMPLETED.
5. **Completion:** When all jobs finish, present a summary report.

## 5. Development Strategy
Implementation will follow a backend-first approach:
1. **Core:** Implement BatchJob, BatchSession, and BatchManager.
2. **Persistence:** Implement state serialization and resume logic.
3. **UI:** Build BatchSetupDialog and BatchProgressDashboard reactive layers.
