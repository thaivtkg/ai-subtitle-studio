import json
import shutil
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from core.project.transcription_context import TranscriptionContext
from core.services.project_service import ProjectService


class TestTranscriptionContextProjectSchema(unittest.TestCase):
    def test_tc107_v1_project_loads_empty_context_without_rewrite(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        video = root / "video.mp4"
        video.write_bytes(b"fake-video")

        service = ProjectService()
        source = service._generate_fingerprint(str(video))
        project_dir = root / "Legacy.ai-subtitle"
        project_dir.mkdir()
        (project_dir / "artifacts").mkdir()

        project_json = {
            "schema_version": 1,
            "project_id": "legacy",
            "name": "Legacy",
            "created_at": "2026-09-02T00:00:00",
            "updated_at": "2026-09-02T00:00:00",
            "source": asdict(source),
        }
        path = project_dir / "project.json"
        path.write_text(json.dumps(project_json), encoding="utf-8")
        before = path.read_bytes()

        project = service.open_project(str(project_dir))

        self.assertEqual(project.transcription_context.context, "")
        self.assertEqual(project.transcription_context.glossary, [])
        self.assertEqual(path.read_bytes(), before)

    def test_tc108_v2_round_trip_preserves_context_and_normalized_glossary(self):
        context = TranscriptionContext(
            context="Trận chiến tại Demacia",
            glossary=[" Demacia ", "demacia", "Lux", "", "Garen"],
        )
        normalized = context.normalized()
        self.assertEqual(normalized.glossary, ["Demacia", "Lux", "Garen"])

        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        video = root / "video.mp4"
        video.write_bytes(b"fake-video")

        service = ProjectService()
        project = service.create_project(str(root), "TestV2", str(video))
        project.transcription_context = context
        service.save_project()

        reopened = service.open_project(service.project_dir)

        self.assertEqual(reopened.transcription_context.context, "Trận chiến tại Demacia")
        self.assertEqual(reopened.transcription_context.glossary, ["Demacia", "Lux", "Garen"])


if __name__ == "__main__":
    unittest.main()
