from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import logging
import shutil
import uuid

from PySide6.QtCore import QObject, Signal

from core.project.source_fingerprint import SourceInfo
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_models import (
    RecoveryCandidate,
    RecoveryContext,
    RecoveryEntry,
    RecoveryManifest,
    RecoverySession,
    RecoveryValidationResult,
    RecoveryWorkingState,
)
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker


logger = logging.getLogger(__name__)


class RecoveryManager(QObject):
    """Own recovery-session files without touching canonical project files."""

    _SLOTS = ("current", "previous", "older")
    _TEMP_ARTIFACTS = (
        "manifest.tmp",
        "snapshot.tmp",
        "manifest.previous.tmp",
        "snapshot.previous.tmp",
        "manifest.older.tmp",
        "snapshot.older.tmp",
    )
    _SEMANTIC_STAGES = (
        "temp_snapshot",
        "temp_manifest",
        "previous_to_older",
        "current_to_previous",
        "before_current_publication",
        "current_snapshot_publication",
        "current_manifest_publication",
    )

    snapshot_written = Signal(str, int)
    session_quarantined = Signal(str, str)

    def __init__(
        self,
        sessions_dir: Path,
        quarantine_dir: Path,
        revision_tracker: RevisionTracker,
        snapshot_store: AtomicSnapshotStore,
        validator: RecoveryValidator,
        parent=None,
    ):
        super().__init__(parent)
        self.sessions_dir = sessions_dir
        self.quarantine_dir = quarantine_dir
        self.revision_tracker = revision_tracker
        self.snapshot_store = snapshot_store
        self.validator = validator
        self._active_session: RecoverySession | None = None

    @property
    def trace_path(self) -> Path:
        return self.sessions_dir.parent / "recovery_snapshot.log"

    def log_runtime_event(self, event: str, **details) -> None:
        """Persist recovery diagnostics without changing recovery behavior."""
        self._trace(event, **details)

    def _trace(self, event: str, **details) -> None:
        values = []
        for key, value in details.items():
            text = str(value).replace("\r", "\\r").replace("\n", "\\n")
            values.append(f"{key}={text}")
        line = (
            f"{self._timestamp()} [RECOVERY-SNAPSHOT] "
            f"stage={event} {' '.join(values)}\n"
        )
        logger.info(line.rstrip())
        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
        except OSError:
            # Diagnostics must never change recovery success/failure semantics.
            return

    def create_session(self, context: RecoveryContext) -> RecoverySession:
        session_id = context.session_id or uuid.uuid4().hex
        directory = self.sessions_dir / session_id
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "active.lock").touch()
        manifest = RecoveryManifest(
            schema_version=1,
            session_id=session_id,
            app_version=context.app_version,
            project_id=context.project_id,
            project_file_path=context.project_file_path,
            video_path=context.video_path,
            source_fingerprint=context.source_fingerprint,
            source_modified_at=context.source_modified_at,
            created_at=self._timestamp(),
            last_snapshot_at=None,
            edit_revision=self.revision_tracker.edit_revision,
            snapshot_revision=self.revision_tracker.snapshot_revision,
            last_saved_revision=self.revision_tracker.last_saved_revision,
            last_clean_revision=self.revision_tracker.last_clean_revision,
        )
        self.snapshot_store.write_json_atomic(directory / "manifest.json", asdict(manifest))
        self._active_session = RecoverySession(session_id, directory, manifest)
        self._trace(
            "session-created",
            session_id=session_id,
            project_id=context.project_id,
            project_file_path=context.project_file_path,
            session_dir=directory,
            edit_revision=manifest.edit_revision,
            snapshot_revision=manifest.snapshot_revision,
        )
        return self._active_session

    def write_snapshot(
        self, state: RecoveryWorkingState, *, force: bool = False
    ) -> bool:
        self._trace(
            "snapshot-attempt",
            session_id=getattr(state, "session_id", None),
            edit_revision=getattr(state, "edit_revision", None),
            force=force,
            active_session_id=(
                self._active_session.session_id if self._active_session else None
            ),
            tracker_edit_revision=self.revision_tracker.edit_revision,
            tracker_snapshot_revision=self.revision_tracker.snapshot_revision,
            dirty=self.revision_tracker.is_dirty,
        )
        if self._active_session is None:
            self._trace("snapshot-skipped", reason="no-active-session")
            return False
        if (
            state.session_id != self._active_session.session_id
            or state.edit_revision != self.revision_tracker.edit_revision
        ):
            self._trace(
                "snapshot-skipped",
                reason="stale-or-wrong-session-state",
                state_session_id=state.session_id,
                active_session_id=self._active_session.session_id,
                state_revision=state.edit_revision,
                tracker_revision=self.revision_tracker.edit_revision,
            )
            return False
        if not force and (
            not self.revision_tracker.is_dirty
            or self.revision_tracker.edit_revision
            <= self.revision_tracker.snapshot_revision
        ):
            self._trace(
                "snapshot-skipped",
                reason="clean-or-no-new-revision",
                edit_revision=self.revision_tracker.edit_revision,
                snapshot_revision=self.revision_tracker.snapshot_revision,
                dirty=self.revision_tracker.is_dirty,
            )
            return False

        revision = state.edit_revision
        directory = self._active_session.directory
        snapshot_path = directory / "snapshot.json"
        manifest_path = directory / "manifest.json"
        updated_manifest = replace(
            self._active_session.manifest,
            edit_revision=revision,
            snapshot_revision=revision,
            last_snapshot_at=self._timestamp(),
        )
        validation = self.validator.validate_data(updated_manifest, state)
        if not validation.is_valid:
            self._trace(
                "snapshot-skipped",
                reason="validation-failed",
                validation_reason=validation.reason,
            )
            return False

        try:
            current_pair = self._read_pair(directory, "current")
        except OSError as error:
            self._trace("snapshot-failed", stage="read-current", error=error)
            return False
        except (TypeError, ValueError):
            current_pair = None
            self._trace("snapshot-history-reset", slot="current")
        try:
            previous_pair = self._read_pair(directory, "previous")
        except OSError as error:
            self._trace("snapshot-failed", stage="read-previous", error=error)
            return False
        except (TypeError, ValueError):
            previous_pair = None
            self._trace("snapshot-history-reset", slot="previous")
        snapshot_tmp = None
        manifest_tmp = None
        stage = "prepare"
        try:
            stage = "temp_snapshot"
            self._before_stage("temp_snapshot")
            snapshot_tmp = self.snapshot_store.write_json_temp(
                snapshot_path, asdict(state)
            )
            stage = "temp_manifest"
            self._before_stage("temp_manifest")
            manifest_tmp = self.snapshot_store.write_json_temp(
                manifest_path, asdict(updated_manifest)
            )

            stage = "previous_to_older"
            self._before_stage("previous_to_older")
            if previous_pair is not None:
                self._write_pair(directory, "older", *previous_pair)

            stage = "current_to_previous"
            self._before_stage("current_to_previous")
            if current_pair is not None:
                self._write_pair(directory, "previous", *current_pair)

            stage = "before_current_publication"
            self._before_stage("before_current_publication")
            stage = "current_snapshot_publication"
            self._before_stage("current_snapshot_publication")
            self.snapshot_store.publish_temp(snapshot_tmp, snapshot_path)
            snapshot_tmp = None

            stage = "current_manifest_publication"
            self._before_stage("current_manifest_publication")
            self.snapshot_store.publish_temp(manifest_tmp, manifest_path)
            manifest_tmp = None
        except (OSError, TypeError, ValueError) as error:
            self._trace("snapshot-failed", stage=stage, error=error)
            return False
        finally:
            for temporary in (snapshot_tmp, manifest_tmp):
                if temporary is not None:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass

        self._active_session = replace(self._active_session, manifest=updated_manifest)
        self.revision_tracker.record_snapshot_success(revision)
        self.snapshot_written.emit(self._active_session.session_id, revision)
        self._trace(
            "snapshot-written",
            session_id=self._active_session.session_id,
            project_id=updated_manifest.project_id,
            revision=revision,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            snapshot_exists=snapshot_path.exists(),
            manifest_exists=manifest_path.exists(),
        )
        return True

    def scan_candidates(self) -> list[RecoveryCandidate]:
        self._trace("scan-start", sessions_dir=self.sessions_dir)
        if not self.sessions_dir.exists():
            self._trace("scan-complete", candidate_count=0, reason="sessions-dir-missing")
            return []
        candidates = []
        for directory in self.sessions_dir.iterdir():
            if not directory.is_dir() or not (directory / "active.lock").exists():
                continue
            valid_pair_found = False
            slot_present = any(
                path.exists()
                for path in (
                    directory / "snapshot.json",
                    directory / "manifest.previous.json",
                    directory / "snapshot.previous.json",
                    directory / "manifest.older.json",
                    directory / "snapshot.older.json",
                )
            )
            last_error = "NO_VALID_RECOVERY_PAIR"
            for slot in self._SLOTS:
                try:
                    pair = self._read_pair(directory, slot)
                except (OSError, ValueError, TypeError) as error:
                    pair = None
                    last_error = str(error)
                if pair is None:
                    continue
                valid_pair_found = True
                manifest, snapshot = pair
                if manifest.snapshot_revision > max(
                    manifest.last_saved_revision, manifest.last_clean_revision
                ):
                    candidates.append(RecoveryCandidate(manifest, snapshot, directory))
                    self._trace(
                        "candidate-found",
                        session_id=manifest.session_id,
                        project_id=manifest.project_id,
                        project_file_path=manifest.project_file_path,
                        revision=manifest.snapshot_revision,
                        directory=directory,
                    )
                    break
            if slot_present and not valid_pair_found:
                self._trace(
                    "candidate-invalid",
                    session_id=directory.name,
                    reason=last_error,
                    directory=directory,
                )
                self.quarantine_session(directory.name, last_error)
        self._trace("scan-complete", candidate_count=len(candidates))
        return candidates

    def list_recovery_entries(
        self,
        *,
        active_session_id: str | None = None,
        source_info_by_project: dict[str | None, SourceInfo | None] | None = None,
    ) -> list[RecoveryEntry]:
        """Return one validated, effective recovery entry per session."""
        source_info_by_project = source_info_by_project or {}
        entries = []
        for candidate in self.scan_candidates():
            manifest = candidate.manifest
            if active_session_id is not None and manifest.session_id == active_session_id:
                continue
            source_info = source_info_by_project.get(manifest.project_id)
            validation = self.validate_candidate(candidate, source_info)
            if not validation.is_valid:
                continue
            source_status = (
                "AVAILABLE" if validation.source_matches else validation.source_reason
            )
            entries.append(
                RecoveryEntry(
                    session_id=manifest.session_id,
                    project_id=manifest.project_id,
                    project_root=manifest.project_file_path,
                    video_path=manifest.video_path,
                    effective_snapshot_timestamp=self._effective_timestamp(manifest),
                    created_at=manifest.created_at,
                    snapshot_revision=manifest.snapshot_revision,
                    last_saved_revision=manifest.last_saved_revision,
                    last_clean_revision=manifest.last_clean_revision,
                    source_status=source_status,
                    unlinked_restore_allowed=source_status != "AVAILABLE",
                    linked_restore_allowed=source_status == "AVAILABLE",
                )
            )
        return sorted(entries, key=self._entry_sort_key)

    def resolve_recovery_candidate(
        self, session_id: str, *, active_session_id: str | None = None
    ) -> RecoveryCandidate | None:
        """Resolve the current effective candidate by stable session identity."""
        if active_session_id is not None and session_id == active_session_id:
            return None
        return next(
            (
                candidate
                for candidate in self.scan_candidates()
                if candidate.manifest.session_id == session_id
            ),
            None,
        )

    def resolve_recovery_entry(
        self,
        session_id: str,
        *,
        active_session_id: str | None = None,
        source_info_by_project: dict[str | None, SourceInfo | None] | None = None,
    ) -> RecoveryEntry | None:
        """Resolve a current filesystem entry by stable session identity."""
        return next(
            (
                entry
                for entry in self.list_recovery_entries(
                    active_session_id=active_session_id,
                    source_info_by_project=source_info_by_project,
                )
                if entry.session_id == session_id
            ),
            None,
        )

    def delete_entry(
        self, session_id: str, *, active_session_id: str | None = None
    ) -> bool:
        """Discard one non-live recovery session; refuse the active session."""
        if active_session_id is not None and session_id == active_session_id:
            return False
        if not (self.sessions_dir / session_id).is_dir():
            return False
        self.discard_session(session_id)
        return True

    def invalidate_snapshot_at_clean_point(self, clean_revision: int) -> None:
        if self._active_session is None:
            return
        manifest = self._active_session.manifest
        if manifest.snapshot_revision > clean_revision:
            return
        updated = replace(manifest, last_clean_revision=clean_revision)
        self.snapshot_store.write_json_atomic(
            self._active_session.directory / "manifest.json", asdict(updated)
        )
        self._remove_snapshot_history(self._active_session.directory)
        self._active_session = replace(self._active_session, manifest=updated)

    def validate_candidate(
        self,
        candidate: RecoveryCandidate,
        actual_source_info: SourceInfo | None = None,
    ) -> RecoveryValidationResult:
        result = self.validator.validate_data(candidate.manifest, candidate.snapshot)
        if not result.is_valid:
            self._trace(
                "candidate-validation-failed",
                session_id=candidate.manifest.session_id,
                project_id=candidate.manifest.project_id,
                reason=result.reason,
            )
            return result
        result = self.validator.validate_source(candidate.manifest, actual_source_info)
        self._trace(
            "candidate-validated",
            session_id=candidate.manifest.session_id,
            project_id=candidate.manifest.project_id,
            valid=result.is_valid,
            source_matches=result.source_matches,
            source_reason=result.source_reason,
        )
        return result

    def handoff_recovered_state(
        self,
        old_candidate: RecoveryCandidate,
        recovered_state: RecoveryWorkingState,
        new_context: RecoveryContext,
    ) -> RecoverySession:
        self._trace(
            "restore-handoff-start",
            old_session_id=old_candidate.manifest.session_id,
            project_id=old_candidate.manifest.project_id,
            revision=recovered_state.edit_revision,
        )
        result = self.validate_candidate(old_candidate)
        if not result.is_valid:
            raise ValueError(result.reason)
        new_session = self.create_session(new_context)
        state = replace(recovered_state, session_id=new_session.session_id)
        try:
            if not self.write_snapshot(state, force=True):
                raise OSError("recovered snapshot was not written")
            snapshot_path = new_session.directory / "snapshot.json"
            if not snapshot_path.exists():
                raise OSError("recovered snapshot is missing")
            committed = self.revision_tracker.snapshot_revision
            if isinstance(committed, int) and committed != state.edit_revision:
                raise OSError("recovered snapshot revision was not committed")
        except (OSError, TypeError, ValueError):
            self._trace(
                "restore-handoff-failed",
                old_session_id=old_candidate.manifest.session_id,
                new_session_id=new_session.session_id,
            )
            self.discard_session(new_session.session_id)
            raise
        self.discard_session(old_candidate.manifest.session_id)
        self._trace(
            "restore-handoff-complete",
            old_session_id=old_candidate.manifest.session_id,
            new_session_id=new_session.session_id,
            project_id=new_context.project_id,
            revision=recovered_state.edit_revision,
        )
        return new_session

    def record_explicit_save(self, revision: int | None = None) -> None:
        if self._active_session is None:
            return
        revision = self.revision_tracker.edit_revision if revision is None else revision
        manifest = replace(
            self._active_session.manifest,
            edit_revision=revision,
            snapshot_revision=revision,
            last_saved_revision=revision,
            last_clean_revision=revision,
            last_snapshot_at=None,
        )
        snapshot_path = self._active_session.directory / "snapshot.json"
        self.snapshot_store.write_json_atomic(
            self._active_session.directory / "manifest.json", asdict(manifest)
        )
        self._remove_snapshot_history(self._active_session.directory)
        self._active_session = replace(self._active_session, manifest=manifest)

    def release_active_session_for_switch(self) -> None:
        """Retire the current session using the current document's dirty state."""
        if self._active_session is None:
            return
        if self.revision_tracker.is_dirty:
            self._active_session = None
            return
        self.finalize_clean_shutdown()

    def discard_session(self, session_id: str) -> None:
        directory = self.sessions_dir / session_id
        if not directory.exists():
            return
        for name in (
            "active.lock",
            "manifest.json",
            "snapshot.json",
            "manifest.previous.json",
            "snapshot.previous.json",
            "manifest.older.json",
            "snapshot.older.json",
            *self._TEMP_ARTIFACTS,
        ):
            (directory / name).unlink(missing_ok=True)
        try:
            directory.rmdir()
        except OSError:
            pass
        if self._active_session and self._active_session.session_id == session_id:
            self._active_session = None

    def finalize_clean_shutdown(self) -> bool:
        if self._active_session is None or self.revision_tracker.is_dirty:
            return False
        self.discard_session(self._active_session.session_id)
        return True

    def quarantine_session(self, session_id: str, reason: str) -> Path:
        source = self.sessions_dir / session_id
        target = self.quarantine_dir / f"{session_id}-{self._timestamp_for_path()}"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(source), str(target))
        except OSError:
            return source
        self.session_quarantined.emit(session_id, reason)
        return target

    @staticmethod
    def _entry_sort_key(entry: RecoveryEntry) -> tuple[float, int, float, str]:
        return (
            -RecoveryManager._timestamp_sort_value(entry.effective_snapshot_timestamp),
            -entry.snapshot_revision,
            -RecoveryManager._timestamp_sort_value(entry.created_at),
            entry.session_id,
        )

    @staticmethod
    def _effective_timestamp(manifest: RecoveryManifest) -> str:
        if RecoveryManager._timestamp_sort_value(manifest.last_snapshot_at) != float(
            "-inf"
        ):
            return manifest.last_snapshot_at or ""
        if RecoveryManager._timestamp_sort_value(manifest.created_at) != float(
            "-inf"
        ):
            return manifest.created_at
        return ""

    @staticmethod
    def _timestamp_sort_value(value: str | None) -> float:
        if not value:
            return float("-inf")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return float("-inf")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    def _before_stage(self, stage: str) -> None:
        callback = getattr(self.snapshot_store, "before_stage", None)
        if callable(callback):
            callback(stage)

    def _slot_paths(self, directory: Path, slot: str) -> tuple[Path, Path]:
        suffix = {"current": "", "previous": ".previous", "older": ".older"}[slot]
        return (
            directory / f"manifest{suffix}.json",
            directory / f"snapshot{suffix}.json",
        )

    def _read_pair(
        self, directory: Path, slot: str
    ) -> tuple[RecoveryManifest, RecoveryWorkingState] | None:
        manifest_path, snapshot_path = self._slot_paths(directory, slot)
        if not manifest_path.exists() or not snapshot_path.exists():
            return None
        manifest = RecoveryManifest(**self.snapshot_store.read_json(manifest_path))
        snapshot = RecoveryWorkingState(**self.snapshot_store.read_json(snapshot_path))
        result = self.validator.validate_data(manifest, snapshot)
        if not result.is_valid:
            return None
        return manifest, snapshot

    def _write_pair(
        self,
        directory: Path,
        slot: str,
        manifest: RecoveryManifest,
        snapshot: RecoveryWorkingState,
    ) -> None:
        manifest_path, snapshot_path = self._slot_paths(directory, slot)
        self.snapshot_store.write_json_atomic(manifest_path, asdict(manifest))
        self.snapshot_store.write_json_atomic(snapshot_path, asdict(snapshot))

    def _remove_snapshot_history(self, directory: Path) -> None:
        for slot in self._SLOTS:
            _, snapshot_path = self._slot_paths(directory, slot)
            snapshot_path.unlink(missing_ok=True)
            if slot != "current":
                manifest_path, _ = self._slot_paths(directory, slot)
                manifest_path.unlink(missing_ok=True)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _timestamp_for_path() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
