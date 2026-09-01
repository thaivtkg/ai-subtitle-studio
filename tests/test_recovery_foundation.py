import os
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from core.project.source_fingerprint import SourceInfo
from core.recovery.recovery_models import (
    RecoveryCandidate,
    RecoveryManifest,
    RecoveryWorkingState,
)
from core.recovery.recovery_validator import RecoveryValidator
from core.runtime.runtime_paths import RuntimePaths
from core.project.source_fingerprint import generate_source_info


def make_manifest() -> RecoveryManifest:
    return RecoveryManifest(
        schema_version=1,
        session_id="session-a",
        app_version="test",
        project_id="project-1",
        project_file_path="C:/project",
        video_path="C:/video.mp4",
        source_fingerprint="abc",
        source_modified_at=1.0,
        created_at="2026-09-01T00:00:00",
        last_snapshot_at="2026-09-01T00:00:30",
        edit_revision=5,
        snapshot_revision=5,
        last_saved_revision=2,
        last_clean_revision=2,
    )


def make_snapshot() -> RecoveryWorkingState:
    return RecoveryWorkingState(
        schema_version=2.0,
        session_id="session-a",
        project_id="project-1",
        project_file_path="C:/project",
        video_path="C:/video.mp4",
        source_fingerprint="abc",
        edit_revision=5,
        segments=[
            {
                "id": "seg-1",
                "stt": "1",
                "start": 1000,
                "end": 2000,
                "text": "hello",
                "status": "draft",
                "metadata": {"type": "normal"},
            }
        ],
        workspace_state={
            "active_page": "editor",
            "active_tab": "inline_editor",
            "selected_segment_id": "seg-1",
            "playback_position_ms": 1200,
            "subtitle_preview_enabled": True,
            "splitter_sizes": [400, 200],
        },
    )


class TestRecoveryPaths(unittest.TestCase):
    def test_recovery_paths_live_under_user_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                root = RuntimePaths.get_user_data_dir()
                self.assertEqual(RuntimePaths.get_recovery_dir(), root / "recovery")
                self.assertEqual(
                    RuntimePaths.get_recovery_sessions_dir(),
                    root / "recovery" / "sessions",
                )
                self.assertEqual(
                    RuntimePaths.get_recovery_quarantine_dir(),
                    root / "recovery" / "quarantine",
                )

    def test_ensure_user_data_dirs_creates_recovery_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}):
                RuntimePaths.ensure_user_data_dirs()
                self.assertTrue(RuntimePaths.get_recovery_sessions_dir().is_dir())
                self.assertTrue(RuntimePaths.get_recovery_quarantine_dir().is_dir())


class TestSourceFingerprint(unittest.TestCase):
    def test_shared_fingerprint_matches_project_source_shape(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"subtitle-source" * 64)
            path = handle.name
        try:
            info = generate_source_info(path)
            self.assertEqual(info.path, path)
            self.assertEqual(info.filename, os.path.basename(path))
            self.assertGreater(info.size_bytes, 0)
            self.assertEqual(len(info.fingerprint), 64)
        finally:
            os.remove(path)


class TestRecoveryValidator(unittest.TestCase):
    def test_revision_mismatch_is_invalid(self):
        manifest = make_manifest()
        snapshot = replace(make_snapshot(), edit_revision=4)
        result = RecoveryValidator().validate_data(manifest, snapshot)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "SNAPSHOT_REVISION_MISMATCH")

    def test_missing_segment_uuid_is_invalid(self):
        manifest = make_manifest()
        snapshot = make_snapshot()
        segments = deepcopy(snapshot.segments)
        segments[0]["id"] = ""
        snapshot = replace(snapshot, segments=segments)
        result = RecoveryValidator().validate_data(manifest, snapshot)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.reason, "INVALID_SEGMENT_SCHEMA")

    def test_source_mismatch_is_handled_correctly(self):
        manifest = make_manifest()
        res_missing = RecoveryValidator().validate_source(manifest, None)
        self.assertTrue(res_missing.is_valid)
        self.assertFalse(res_missing.source_matches)
        self.assertEqual(res_missing.source_reason, "SOURCE_MISSING")

        fake_source = SourceInfo("C:/video.mp4", "video.mp4", 100, 1.0, "def")
        res_mismatch = RecoveryValidator().validate_source(manifest, fake_source)
        self.assertTrue(res_mismatch.is_valid)
        self.assertFalse(res_mismatch.source_matches)
        self.assertEqual(res_mismatch.source_reason, "SOURCE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
