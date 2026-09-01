from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid

from PySide6.QtCore import QObject, Signal

from core.project.source_fingerprint import SourceInfo
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_models import (
    RecoveryCandidate,
    RecoveryContext,
    RecoveryManifest,
    RecoverySession,
    RecoveryValidationResult,
    RecoveryWorkingState,
)
from core.recovery.recovery_validator import RecoveryValidator
from core.recovery.revision_tracker import RevisionTracker


class RecoveryManager(QObject):
    """Own recovery-session files without touching canonical project files."""

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
        return self._active_session

    def write_snapshot(
        self, state: RecoveryWorkingState, *, force: bool = False
    ) -> bool:
        if self._active_session is None:
            return False
        if (
            state.session_id != self._active_session.session_id
            or state.edit_revision != self.revision_tracker.edit_revision
        ):
            return False
        if not force and (
            not self.revision_tracker.is_dirty
            or self.revision_tracker.edit_revision
            <= self.revision_tracker.snapshot_revision
        ):
            return False

        revision = state.edit_revision
        directory = self._active_session.directory
        snapshot_path = directory / "snapshot.json"
        previous_snapshot = (
            self.snapshot_store.read_json(snapshot_path)
            if snapshot_path.exists()
            else None
        )
        updated_manifest = replace(
            self._active_session.manifest,
            edit_revision=revision,
            snapshot_revision=revision,
            last_snapshot_at=self._timestamp(),
        )
        try:
            self.snapshot_store.write_json_atomic(snapshot_path, asdict(state))
            self.snapshot_store.write_json_atomic(
                directory / "manifest.json", asdict(updated_manifest)
            )
        except (OSError, TypeError, ValueError):
            try:
                if previous_snapshot is None:
                    snapshot_path.unlink(missing_ok=True)
                else:
                    self.snapshot_store.write_json_atomic(
                        snapshot_path, previous_snapshot
                    )
            except OSError:
                pass
            return False

        self._active_session = replace(self._active_session, manifest=updated_manifest)
        self.revision_tracker.record_snapshot_success(revision)
        self.snapshot_written.emit(self._active_session.session_id, revision)
        return True

    def scan_candidates(self) -> list[RecoveryCandidate]:
        if not self.sessions_dir.exists():
            return []
        candidates = []
        for directory in self.sessions_dir.iterdir():
            if not directory.is_dir() or not (directory / "active.lock").exists():
                continue
            manifest_path = directory / "manifest.json"
            snapshot_path = directory / "snapshot.json"
            if not manifest_path.exists() or not snapshot_path.exists():
                continue
            try:
                manifest = RecoveryManifest(**self.snapshot_store.read_json(manifest_path))
                snapshot = RecoveryWorkingState(**self.snapshot_store.read_json(snapshot_path))
                result = self.validator.validate_data(manifest, snapshot)
                if not result.is_valid:
                    raise ValueError(result.reason)
            except (OSError, ValueError, TypeError) as error:
                self.quarantine_session(directory.name, str(error))
                continue
            if manifest.snapshot_revision > max(
                manifest.last_saved_revision, manifest.last_clean_revision
            ):
                candidates.append(RecoveryCandidate(manifest, snapshot, directory))
        return candidates

    def validate_candidate(
        self,
        candidate: RecoveryCandidate,
        actual_source_info: SourceInfo | None = None,
    ) -> RecoveryValidationResult:
        result = self.validator.validate_data(candidate.manifest, candidate.snapshot)
        if not result.is_valid:
            return result
        return self.validator.validate_source(candidate.manifest, actual_source_info)

    def handoff_recovered_state(
        self,
        old_candidate: RecoveryCandidate,
        recovered_state: RecoveryWorkingState,
        new_context: RecoveryContext,
    ) -> RecoverySession:
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
            self.discard_session(new_session.session_id)
            raise
        self.discard_session(old_candidate.manifest.session_id)
        return new_session

    def record_explicit_save(self) -> None:
        if self._active_session is None:
            return
        revision = self.revision_tracker.edit_revision
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
        snapshot_path.unlink(missing_ok=True)
        self.revision_tracker.record_explicit_save_success()
        self._active_session = replace(self._active_session, manifest=manifest)

    def discard_session(self, session_id: str) -> None:
        directory = self.sessions_dir / session_id
        if not directory.exists():
            return
        for name in ("active.lock", "snapshot.json", "manifest.json"):
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
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _timestamp_for_path() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
