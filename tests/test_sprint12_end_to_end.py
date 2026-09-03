import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from core.artifacts.artifact_store import ArtifactStore
from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportResult
from core.media_import.media_import_service import MediaImportService
from core.media_import.media_probe import ProbeResult
from core.media_import.url_classifier import MediaURLType
from core.queue_manager import QueueManager
from core.services.project_service import ProjectService
from core.timing.timing_batch_service import TimingBatchService
from ui.dialogs.media_import_dialog import MODE_NEW_PROJECT, MediaImportDialog, MediaImportDialogState

try:
    from ui.subtitle_generation_panel import SubtitleGenerationPanel
except (ImportError, ModuleNotFoundError):
    SubtitleGenerationPanel = None

try:
    from ui.Gui import MainWindow
except (ImportError, ModuleNotFoundError, OSError):
    MainWindow = None


class FakeSafetyPolicy:
    def validate_url(self, url):
        return SimpleNamespace(original_url=url)


class FakeURLClassifier:
    def classify(self, url):
        return MediaURLType.DIRECT_MEDIA


class FakeDownloadAdapter:
    def download(self, target, dest_path, progress_callback=None, cancel_flag=None):
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"fake-video-content-for-sprint-12")
        return MediaImportResult(
            str(dest_path), target.original_url, dest_path.name,
            dest_path.stat().st_size, "video/mp4", {},
        )


class FakeProbe:
    def probe(self, file_path):
        return ProbeResult(True, "h264", 12.0, 1920, 1080,
                           "mov,mp4,m4a,3gp,3g2,mj2", ".mp4")


class FailingProbe:
    def probe(self, file_path):
        raise MediaImportError(MediaImportErrorCode.NO_VIDEO_STREAM, "No video stream")


class TestSprint12ProjectOwnedImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _service(self, probe=None):
        return MediaImportService(
            safety_policy=FakeSafetyPolicy(),
            url_classifier=FakeURLClassifier(),
            direct_adapter=FakeDownloadAdapter(),
            ytdlp_adapter=MagicMock(),
            media_probe=probe or FakeProbe(),
            storage_root=self.root / "queue-only-storage",
        )

    def test_tc124_project_media_is_finalized_inside_bundle(self):
        bundle = self.root / "Demo.ai-subtitle"
        result = self._service().import_from_url(
            "https://example.com/video.mp4", destination_dir=bundle / "media"
        )
        project_service = ProjectService(ArtifactStore())
        project = project_service.create_project(str(bundle), "Demo", result.local_path)
        expected = bundle / "media" / "source.mp4"
        self.assertEqual(Path(result.local_path).resolve(), expected.resolve())
        self.assertEqual(Path(project.source.path).resolve(), expected.resolve())
        self.assertTrue(project.source.fingerprint)
        self.assertNotIn(self.root / "queue-only-storage", expected.parents)

    def test_failure_cleans_up_empty_bundle_and_allows_retry(self):
        bundle = self.root / "RetryProject.ai-subtitle"
        media_dir = bundle / "media"
        with self.assertRaises(MediaImportError) as ctx:
            self._service(FailingProbe()).import_from_url(
                "https://example.com/video.mp4", destination_dir=media_dir
            )
        self.assertEqual(ctx.exception.code, MediaImportErrorCode.NO_VIDEO_STREAM)
        self.assertFalse(media_dir.exists())

    def test_tc126_timing_uses_project_source_path(self):
        _, result, project_service, _ = self._create_project_for_test()
        service = TimingBatchService(project_service)
        with patch("core.timing.timing_batch_service.TimingBatchWorker") as worker_cls:
            worker_cls.return_value = MagicMock()
            service._execute_run(0, 10, {"model_size": "base", "compute_type": "float16"})
            request = worker_cls.call_args.args[0]
        self.assertEqual(Path(request.video_path).resolve(), Path(result.local_path).resolve())

    @unittest.skipIf(SubtitleGenerationPanel is None, "SubtitleGenerationPanel unavailable")
    def test_tc127_full_subtitle_uses_project_source_path(self):
        _, result, project_service, _ = self._create_project_for_test()
        generation_service = MagicMock()
        generation_service.project_service = project_service
        generation_service.checkpoint_manager.load_checkpoint.return_value = None
        generation_service.is_running = False
        generation_service.compile_prompt_context.return_value = SimpleNamespace(text="")
        panel = SubtitleGenerationPanel(generation_service)
        panel.set_video_duration(12_000)
        panel._on_generate_clicked()
        request = generation_service.start_generation.call_args.args[0]
        self.assertEqual(Path(request.video_path).resolve(), Path(result.local_path).resolve())

    def _create_project_for_test(self):
        bundle = self.root / "Demo.ai-subtitle"
        result = self._service().import_from_url(
            "https://example.com/video.mp4", destination_dir=bundle / "media"
        )
        project_service = ProjectService(ArtifactStore())
        project = project_service.create_project(str(bundle), "Demo", result.local_path)
        return bundle, result, project_service, project

    def test_new_project_cancel_or_failure_removes_empty_bundle(self):
        bundle = self.root / "RetryProject.ai-subtitle"
        dialog = MediaImportDialog(self._service(), mode=MODE_NEW_PROJECT)
        dialog.url_input.setText("https://example.com/video.mp4")
        dialog.project_name_input.setText("RetryProject")
        dialog.location_input.setText(str(self.root))
        self.assertTrue(dialog._prepare_destination())
        dialog._destination_dir.mkdir(parents=True, exist_ok=True)
        dialog.current_state = MediaImportDialogState.CANCELLED
        dialog._on_worker_thread_finished()
        self.assertFalse(bundle.exists())
        self.assertTrue(dialog._prepare_destination())
        dialog._destination_dir.mkdir(parents=True, exist_ok=True)
        dialog.current_state = MediaImportDialogState.FAILED
        dialog._on_worker_thread_finished()
        self.assertFalse(bundle.exists())
        self.assertTrue(dialog._prepare_destination())


class TestQueueOnlyUrlImport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.media_imports_dir = self.root / "media_imports"
        self.media_imports_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_default_service(self):
        return MediaImportService(
            safety_policy=FakeSafetyPolicy(),
            url_classifier=FakeURLClassifier(),
            direct_adapter=FakeDownloadAdapter(),
            ytdlp_adapter=MagicMock(),
            media_probe=FakeProbe(),
            storage_root=self.media_imports_dir,
        )

    def test_tc130_default_import_uses_durable_runtime_paths(self):
        result = self._make_default_service().import_from_url(
            "https://example.com/video.mp4", destination_dir=None
        )
        actual_path = Path(result.local_path).resolve()
        expected_root = self.media_imports_dir.resolve()

        self.assertEqual(actual_path.parent.parent, expected_root)
        self.assertEqual(actual_path.name, "source.mp4")
        self.assertTrue(actual_path.is_file())
        self.assertNotIn(".ai-subtitle", str(actual_path))

    def test_tc130_remove_queue_item_does_not_delete_media(self):
        result = self._make_default_service().import_from_url(
            "https://example.com/video.mp4", destination_dir=None
        )
        media = Path(result.local_path)
        self.assertTrue(media.exists())

        queue = QueueManager()
        self.assertTrue(queue.add_video(str(media)))
        queue.remove_video(str(media))

        self.assertTrue(media.exists())


@unittest.skipIf(MainWindow is None, "ui.Gui unavailable in this environment")
class TestSprint12MainWindowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("ui.Gui.MediaImportDialog")
    def test_tc125_new_project_url_loads_same_source_into_player(self, dialog_cls):
        bundle = self.root / "PlayerDemo.ai-subtitle"
        source = bundle / "media" / "source.mp4"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"fake-video-content")
        result = MediaImportResult(str(source), "https://example.com/video.mp4",
                                   "source.mp4", source.stat().st_size, "video/mp4", {})
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.get_result.return_value = result
        dialog.get_project_data.return_value = {
            "name": "PlayerDemo", "bundle_path": str(bundle), "media_dir": str(source.parent)
        }
        dialog_cls.return_value = dialog
        project_service = ProjectService(ArtifactStore())
        window = MainWindow(project_service=project_service, media_import_service=MagicMock())
        window.video_player = MagicMock()
        for method in ("_switch_recovery_session", "_refresh_transcription_context_views"):
            setattr(window, method, MagicMock())
        window.workspace_service.restore_workspace = MagicMock()
        window.generation_panel.check_resumable_state = MagicMock()
        window.revision_tracker.reset_for_new_document = MagicMock()
        window._on_new_from_url()
        self.assertEqual(Path(project_service.current_project.source.path).resolve(), source.resolve())
        window.video_player.load_video.assert_called_with(str(source))
        window.close()


if __name__ == "__main__":
    unittest.main()
