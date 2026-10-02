import dataclasses
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)


class FakeWhisperModel:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return [], MagicMock(language="en")


def make_request(prompt_context=""):
    return SubtitleGenerationRequest(
        request_id="req_1",
        project_id="project_1",
        source_fingerprint="source_1",
        video_path="dummy.mp4",
        model_size="tiny",
        compute_type="int8",
        language="en",
        use_vad=False,
        min_silence_ms=500,
        word_timestamps=False,
        prompt_context=prompt_context,
    )


class TestContextualWhisper(unittest.TestCase):
    def setUp(self):
        self.fake_model = FakeWhisperModel()
        self.service = FasterWhisperService(device="cpu")
        self.service.model = self.fake_model
        self.temp_dir = tempfile.mkdtemp()
        self.service._extract_batch_audio = lambda request, batch: (
            "dummy.wav",
            self.temp_dir,
        )
        self.batch = SubtitleGenerationBatch(
            batch_id="batch_1",
            start_ms=0,
            end_ms=1000,
            status="PENDING",
            revision=0,
            created_at="now",
            updated_at="now",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tc112_exact_prompt_reaches_whisper(self):
        self.service.transcribe_batch(
            make_request("Terminology: Demacia."), self.batch, lambda: False
        )

        self.assertEqual(
            self.fake_model.kwargs["initial_prompt"], "Terminology: Demacia."
        )

    def test_tc111_empty_prompt_omits_initial_prompt(self):
        self.service.transcribe_batch(make_request(), self.batch, lambda: False)

        self.assertTrue(
            "initial_prompt" not in self.fake_model.kwargs
            or self.fake_model.kwargs["initial_prompt"] is None
        )

    def test_tc113_resume_request_preserves_immutable_prompt(self):
        original = make_request("Terminology: P.")
        checkpoint_data = dataclasses.asdict(original)
        resumed = SubtitleGenerationRequest(**checkpoint_data)

        self.assertEqual(resumed.prompt_context, "Terminology: P.")
        self.assertNotEqual(resumed.prompt_context, "Terminology: P2.")


if __name__ == "__main__":
    unittest.main()
