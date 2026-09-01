from core.project.source_fingerprint import SourceInfo
from core.recovery.recovery_models import (
    RecoveryManifest,
    RecoveryValidationResult,
    RecoveryWorkingState,
)


class RecoveryValidator:
    def validate_data(
        self,
        manifest: RecoveryManifest,
        snapshot: RecoveryWorkingState,
    ) -> RecoveryValidationResult:
        if manifest.schema_version != 1:
            return RecoveryValidationResult(False, "MANIFEST_SCHEMA_MISMATCH")
        if snapshot.schema_version < 2.0:
            return RecoveryValidationResult(False, "SNAPSHOT_SCHEMA_MISMATCH")
        if manifest.session_id != snapshot.session_id:
            return RecoveryValidationResult(False, "SESSION_ID_MISMATCH")
        if manifest.snapshot_revision != snapshot.edit_revision:
            return RecoveryValidationResult(False, "SNAPSHOT_REVISION_MISMATCH")

        for segment in snapshot.segments:
            if not isinstance(segment, dict):
                return RecoveryValidationResult(False, "INVALID_SEGMENT_SCHEMA")
            if not segment.get("id") or not segment.get("stt"):
                return RecoveryValidationResult(False, "INVALID_SEGMENT_SCHEMA")

        return RecoveryValidationResult(True)

    def validate_source(
        self,
        manifest: RecoveryManifest,
        actual_source_info: SourceInfo | None,
    ) -> RecoveryValidationResult:
        if actual_source_info is None:
            return RecoveryValidationResult(
                True,
                source_matches=False,
                source_reason="SOURCE_MISSING",
            )
        if actual_source_info.fingerprint != manifest.source_fingerprint:
            return RecoveryValidationResult(
                True,
                source_matches=False,
                source_reason="SOURCE_MISMATCH",
            )
        return RecoveryValidationResult(True)
