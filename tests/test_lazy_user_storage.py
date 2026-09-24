import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_service import MediaImportService
from core.media_import.url_classifier import MediaURLType
from core.recovery.atomic_snapshot_store import AtomicSnapshotStore
from core.recovery.recovery_manager import RecoveryManager
from core.recovery.recovery_validator import RecoveryValidator
from core.runtime.runtime_paths import RuntimePaths
from core.services.model_manager import ModelManager


class LazyUserStorageContracts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.local_app_data = Path(self.temp_dir.name)
        self.user_data = self.local_app_data / RuntimePaths.APP_NAME
        self.models_dir = self.user_data / "models"
        self.media_imports_dir = self.user_data / "media_imports"
        self.local_app_data.mkdir(parents=True, exist_ok=True)
        self.env_patch = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local_app_data)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_early_storage_preparation_does_not_touch_models(self):
        self.user_data.mkdir()
        self.models_dir.write_text("not a directory", encoding="utf-8")

        try:
            RuntimePaths.ensure_user_data_dirs()
        except OSError as error:
            self.fail(f"startup preparation touched optional models storage: {error!r}")

        self.assertTrue(self.models_dir.is_file())

    def test_early_storage_preparation_does_not_create_media_imports(self):
        RuntimePaths.ensure_user_data_dirs()

        self.assertFalse(self.media_imports_dir.exists())

    def test_models_path_getter_is_pure(self):
        self.assertEqual(RuntimePaths.get_models_dir(), self.models_dir)
        self.assertFalse(self.user_data.exists())

    def test_model_discovery_handles_missing_storage_without_creating_it(self):
        try:
            discovered = ModelManager.get_discovery_list()
        except OSError as error:
            self.fail(f"model discovery must tolerate missing storage: {error!r}")

        self.assertTrue(discovered)
        self.assertTrue(all(model["installed"] is False for model in discovered))
        self.assertFalse(self.models_dir.exists())

    def test_model_download_prepares_storage_before_calling_downloader(self):
        observed = []

        def fake_download(_model_size, *, cache_dir):
            observed.append(Path(cache_dir).is_dir())

        fake_module = types.ModuleType("faster_whisper")
        fake_module.download_model = fake_download
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with patch.object(RuntimePaths, "get_models_dir", return_value=self.models_dir):
                ModelManager.download_model_sync("tiny")

        self.assertEqual(observed, [True])

    def test_offline_model_import_creates_models_storage_when_needed(self):
        source_dir = self.local_app_data / "offline-model"
        source_dir.mkdir()
        (source_dir / "config.json").write_text("{}", encoding="utf-8")
        (source_dir / "model.bin").write_bytes(b"model")

        with patch.object(RuntimePaths, "get_models_dir", return_value=self.models_dir):
            self.assertTrue(ModelManager.import_offline_model("tiny", str(source_dir)))

        self.assertTrue((self.models_dir / "tiny" / "config.json").is_file())
        self.assertTrue((self.models_dir / "tiny" / "model.bin").is_file())

    def test_model_storage_permission_error_stays_at_model_operation_boundary(self):
        self.models_dir.parent.mkdir(parents=True)
        permission_error = PermissionError(5, "Access is denied", str(self.models_dir))
        downloader = Mock()

        def deny_models_mkdir(path, *args, **kwargs):
            if path == self.models_dir:
                raise permission_error
            return original_mkdir(path, *args, **kwargs)

        original_mkdir = Path.mkdir
        fake_module = types.ModuleType("faster_whisper")
        fake_module.download_model = downloader
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with patch.object(RuntimePaths, "get_models_dir", return_value=self.models_dir):
                with patch.object(Path, "mkdir", autospec=True, side_effect=deny_models_mkdir):
                    try:
                        ModelManager.download_model_sync("tiny")
                    except Exception as error:
                        raised_error = error
                    else:
                        self.fail("model download must report models storage preparation failure")

        cause = raised_error
        while cause is not None and cause is not permission_error:
            cause = cause.__cause__ or cause.__context__
        self.assertIs(cause, permission_error)
        self.assertEqual(Path(permission_error.filename), self.models_dir)
        downloader.assert_not_called()

    def test_model_path_file_fails_before_downloader_runs(self):
        self.models_dir.parent.mkdir(parents=True)
        self.models_dir.write_text("not a directory", encoding="utf-8")
        downloader = Mock()
        fake_module = types.ModuleType("faster_whisper")
        fake_module.download_model = downloader

        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            with patch.object(RuntimePaths, "get_models_dir", return_value=self.models_dir):
                try:
                    ModelManager.download_model_sync("tiny")
                except Exception as error:
                    raised_error = error
                else:
                    self.fail("model download must reject a file occupying models storage")

        cause = raised_error
        while cause is not None and not (
            isinstance(cause, OSError) and cause.filename == str(self.models_dir)
        ):
            cause = cause.__cause__ or cause.__context__
        self.assertIsNotNone(cause)
        downloader.assert_not_called()

    def _make_media_service(self, storage_root):
        class StopAfterStoragePrepared:
            def download(inner_self, *_args, **_kwargs):
                inner_self.root_was_ready = storage_root.is_dir()
                raise MediaImportError(
                    MediaImportErrorCode.DOWNLOAD_CANCELLED,
                    "stop after storage preparation",
                )

        adapter = StopAfterStoragePrepared()
        service = MediaImportService(
            safety_policy=SimpleNamespace(
                validate_url=lambda url: SimpleNamespace(original_url=url)
            ),
            url_classifier=SimpleNamespace(
                classify=lambda _url: MediaURLType.DIRECT_MEDIA
            ),
            direct_adapter=adapter,
            ytdlp_adapter=object(),
            media_probe=object(),
            storage_root=storage_root,
        )
        return service, adapter

    def test_media_service_constructor_does_not_create_storage(self):
        service, _adapter = self._make_media_service(self.media_imports_dir)

        self.assertIsInstance(service, MediaImportService)
        self.assertFalse(self.media_imports_dir.exists())

    def test_media_import_prepares_storage_before_downloading(self):
        service, adapter = self._make_media_service(self.media_imports_dir)
        if self.media_imports_dir.exists():
            import shutil
            shutil.rmtree(self.media_imports_dir)

        with self.assertRaises(MediaImportError) as raised:
            service.import_from_url("https://example.test/video.mp4")

        self.assertEqual(raised.exception.code, MediaImportErrorCode.DOWNLOAD_CANCELLED)
        self.assertTrue(adapter.root_was_ready)

    def test_media_storage_permission_is_reported_as_import_error(self):
        service, _adapter = self._make_media_service(self.media_imports_dir)
        permission_error = PermissionError(
            5, "Access is denied", str(self.media_imports_dir)
        )
        original_mkdir = Path.mkdir

        def deny_storage_mkdir(path, *args, **kwargs):
            if path.name == ".staging":
                raise permission_error
            return original_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", autospec=True, side_effect=deny_storage_mkdir):
            try:
                service.import_from_url("https://example.test/video.mp4")
            except MediaImportError as error:
                raised_error = error
            except OSError as error:
                self.fail(f"storage failure escaped the media-import boundary: {error!r}")
            else:
                self.fail("media import should report storage preparation failure")

        self.assertEqual(raised_error.code, MediaImportErrorCode.PERMISSION_DENIED)
        self.assertIsInstance(raised_error.__cause__, PermissionError)
        reported_values = [str(raised_error), *map(str, raised_error.details.values())]
        self.assertTrue(any(str(self.media_imports_dir) in value for value in reported_values))

    def test_recovery_startup_scan_tolerates_missing_sessions_directory(self):
        recovery_root = self.user_data / "recovery"
        recovery_root.mkdir(parents=True)
        sessions_dir = recovery_root / "sessions"
        manager = RecoveryManager(
            sessions_dir,
            recovery_root / "quarantine",
            Mock(),
            AtomicSnapshotStore(),
            RecoveryValidator(),
        )

        self.assertEqual(manager.scan_candidates(), [])
        self.assertFalse(sessions_dir.exists())


if __name__ == "__main__":
    unittest.main()
