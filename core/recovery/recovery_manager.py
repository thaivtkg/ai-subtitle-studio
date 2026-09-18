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
        manifest_path = directory / "manifest.json"
        updated_manifest = replace(
            self._active_session.manifest,
            edit_revision=revision,
            snapshot_revision=revision,
            last_snapshot_at=self._timestamp(),
        )
        validation = self.validator.validate_data(updated_manifest, state)
        if not validation.is_valid:
            return False

        try:
            current_pair = self._read_pair(directory, "current")
        except OSError:
            return False
        except (TypeError, ValueError):
            current_pair = None
        try:
            previous_pair = self._read_pair(directory, "previous")
        except OSError:
            return False
        except (TypeError, ValueError):
            previous_pair = None
        snapshot_tmp = None
        manifest_tmp = None
        try:
            self._before_stage("temp_snapshot")
            snapshot_tmp = self.snapshot_store.write_json_temp(
                snapshot_path, asdict(state)
            )
            self._before_stage("temp_manifest")
            manifest_tmp = self.snapshot_store.write_json_temp(
                manifest_path, asdict(updated_manifest)
            )

            self._before_stage("previous_to_older")
            if previous_pair is not None:
                self._write_pair(directory, "older", *previous_pair)

            self._before_stage("current_to_previous")
            if current_pair is not None:
                self._write_pair(directory, "previous", *current_pair)

            self._before_stage("before_current_publication")
            self._before_stage("current_snapshot_publication")
            self.snapshot_store.publish_temp(snapshot_tmp, snapshot_path)
            snapshot_tmp = None

            self._before_stage("current_manifest_publication")
            self.snapshot_store.publish_temp(manifest_tmp, manifest_path)
            manifest_tmp = None
        except (OSError, TypeError, ValueError):
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
        return True

    def scan_candidates(self) -> list[RecoveryCandidate]:
        if not self.sessions_dir.exists():
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
                    break
            if slot_present and not valid_pair_found:
                self.quarantine_session(directory.name, last_error)
        return candidates

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
        self._remove_snapshot_history(self._active_session.directory)
        self.revision_tracker.record_explicit_save_success()
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
