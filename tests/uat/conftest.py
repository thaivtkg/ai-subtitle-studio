import os
import sys
import shutil
import tempfile
import pytest
from PySide6.QtWidgets import QApplication
from core.project.project import Project, SourceInfo
from core.project.project_state import ProjectState
from core.services.project_service import ProjectService
from core.artifacts.artifact_store import ArtifactStore
from core.subtitle_generation.generation_service import SubtitleGenerationService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from ui.SubEditor import SubtitleEditorWidget
from ui.Gui import MainWindow

# Ensure QApplication exists
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def temp_project_dir():
    temp_dir = tempfile.mkdtemp(prefix="agy_uat_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

class MockProjectService(ProjectService):
    def __init__(self, project_dir):
        super().__init__(ArtifactStore())
        self.project_dir = project_dir
        self.current_project = Project(
            project_id="uat_proj_1",
            name="UAT Project",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            source=SourceInfo(path="video.mp4", filename="video.mp4", size_bytes=1000, modified_at=0.0, fingerprint="video_hash_1"),
            state=ProjectState()
        )
        self.artifact_store.project_dir = project_dir

class MockWorker:
    def isRunning(self):
        return False

def generate_fake_segments(count, start_ms=0):
    return [
        {
            "id": f"seg_{i}",
            "start": start_ms + i * 2000,
            "end": start_ms + i * 2000 + 1500,
            "text": f"Fake subtitle {i}",
            "stt": str(i + 1),
            "source": "auto"
        }
        for i in range(count)
    ]

@pytest.fixture
def gen_service(temp_project_dir):
    project_service = MockProjectService(temp_project_dir)
    service = SubtitleGenerationService(None, project_service)
    service.current_request = SubtitleGenerationRequest(request_id="req_1", project_id="uat_proj_1", source_fingerprint="video_hash_1", video_path="video.mp4", model_size="base", compute_type="int8", language="en", use_vad=False, min_silence_ms=500, word_timestamps=False, batch_mode="time")
    return service

@pytest.fixture
def main_window(qapp, temp_project_dir):
    window = MainWindow(project_service=MockProjectService(temp_project_dir))
    return window
