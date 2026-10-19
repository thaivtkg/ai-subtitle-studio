import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from core.project.transcription_context import TranscriptionContext
from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_request import (
    SubtitleGenerationRequest,
)
from core.transcription.glossary_extractor import (
    _MAGICAL_GIRL_ROLE_GLOSSARY,
    extract_glossary_offline,
)
from core.transcription.prompt_context_builder import PromptContextBuilder
from core.transcription.token_counter import ApproximateTokenCounter


class FakeWhisperModel:
    def __init__(self):
        self.kwargs = None

    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return [], MagicMock(language=kwargs.get("language", "ja"))


class BiasedWhisperInferenceEngine:
    """
    Simulates Whisper's decoder behavior under prompt conditioning:
    - Without initial_prompt (Scenario A): Free probability decoding produces
      homophone drift or slurred spelling: 'Zenpai, tasukete!' or 'Sen pai'.
    - With initial_prompt containing '先輩, 後輩' or 'Tiền bối, Senpai' (Scenario B):
      Biased logits force correct canonical terminology: '先輩、助けて！'
    """

    def __init__(self):
        self.kwargs = None

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        prompt = kwargs.get("initial_prompt") or ""

        class Segment:
            def __init__(self, text, start=0.0, end=3.0):
                self.text = text
                self.start = start
                self.end = end
                self.words = []

        if "先輩" in prompt:
            segments = [Segment("先輩、助けて！")]
        elif any(k in prompt for k in ["Tiền bối", "Senpai"]):
            segments = [Segment("Tiền bối, cứu tớ với!")]
        else:
            segments = [Segment("Zenpai, tasukete!")]

        class Info:
            language = kwargs.get("language", "ja")
            duration = 3.0

        return segments, Info()


class TestGlossaryPromptABInfluence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.token_counter = ApproximateTokenCounter()
        self.prompt_builder = PromptContextBuilder(self.token_counter)

        self.service = FasterWhisperService(device="cpu")
        self.fake_model = FakeWhisperModel()
        self.service.model = self.fake_model
        self.service._extract_batch_audio = lambda request, batch: (
            "dummy_schoolgirl_audio.wav",
            self.temp_dir,
        )

        self.batch = SubtitleGenerationBatch(
            batch_id="batch_1",
            start_ms=0,
            end_ms=3000,
            status="PENDING",
            revision=0,
            created_at="now",
            updated_at="now",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # Acceptance Criterion 1: Upgrade _MAGICAL_GIRL_ROLE_GLOSSARY
    # =========================================================================
    def test_magical_girl_role_glossary_contains_all_japanese_school_honorifics(self):
        vi_roles = _MAGICAL_GIRL_ROLE_GLOSSARY.get("vi", [])
        ja_roles = _MAGICAL_GIRL_ROLE_GLOSSARY.get("ja", [])

        # Vietnamese role terms
        for term in ["Tiền bối", "Hậu bối", "Senpai", "Kouhai", "Tớ", "Cậu", "Biến hình", "Phép thuật", "Quái vật"]:
            self.assertIn(term, vi_roles)

        # Japanese role terms
        for term in ["先輩", "後輩", "お姉さま", "先生"]:
            self.assertIn(term, ja_roles)

    # =========================================================================
    # Acceptance Criterion 2 & Tier 1: Contract & Payload Pipeline Test
    # =========================================================================
    def test_tier1_scenario_a_no_summary_omits_initial_prompt(self):
        """Kịch bản A (No Summary): initial_prompt rỗng, không chứa từ khóa Senpai/Kouhai."""
        summary = ""
        context = TranscriptionContext(context=summary, glossary=[])
        compiled = self.prompt_builder.build(context)

        self.assertEqual(compiled.text, "")

        request = SubtitleGenerationRequest(
            request_id="req_a",
            project_id="proj_a",
            source_fingerprint="fp_a",
            video_path="audio_clip.mp4",
            model_size="tiny",
            compute_type="int8",
            language="ja",
            use_vad=False,
            min_silence_ms=500,
            word_timestamps=False,
            prompt_context=compiled.text,
        )

        self.service.transcribe_batch(request, self.batch, lambda: False)

        # Assert initial_prompt is omitted or None
        initial_prompt = (self.fake_model.kwargs or {}).get("initial_prompt")
        self.assertTrue(initial_prompt is None or initial_prompt == "")

        # Confirm absolute absence of Senpai/Kouhai tokens
        for forbidden in ["Senpai", "Kouhai", "Tiền bối", "Hậu bối", "先輩", "後輩"]:
            self.assertNotIn(forbidden, str(self.fake_model.kwargs))

    def test_tier1_scenario_b_with_precure_summary_biases_initial_prompt_top_priority(self):
        """Kịch bản B: Summary Precure chiến đấu -> initial_prompt bắt buộc chứa đúng bộ từ khóa ở top."""
        summary = "Precure cùng các tiền bối và hậu bối biến hình chiến đấu tiêu diệt quái vật"

        # 1. GlossaryExtractor trích xuất
        terms_vi = extract_glossary_offline(summary, video_language="vi")
        self.assertIn("Tiền bối", terms_vi)
        self.assertIn("Hậu bối", terms_vi)
        self.assertIn("Senpai", terms_vi)
        self.assertIn("Kouhai", terms_vi)
        self.assertIn("Precure", terms_vi)

        # 2. Xếp ở vị trí đầu tiên của danh sách từ mồi
        top_terms = terms_vi[:9]
        expected_top = ["Tiền bối", "Hậu bối", "Senpai", "Kouhai", "Tớ", "Cậu", "Biến hình", "Phép thuật", "Quái vật"]
        self.assertEqual(top_terms, expected_top)

        # 3. PromptContextBuilder compile
        context_vi = TranscriptionContext(context=summary, glossary=terms_vi)
        compiled_vi = self.prompt_builder.build(context_vi)

        expected_prompt_prefix = "Terminology: Tiền bối, Hậu bối, Senpai, Kouhai, Tớ, Cậu, Biến hình, Phép thuật, Quái vật"
        self.assertTrue(compiled_vi.text.startswith(expected_prompt_prefix))

        # 4. Truyền vào FasterWhisperService -> model.transcribe(..., initial_prompt=...)
        request_vi = SubtitleGenerationRequest(
            request_id="req_b_vi",
            project_id="proj_b",
            source_fingerprint="fp_b",
            video_path="audio_clip.mp4",
            model_size="tiny",
            compute_type="int8",
            language="vi",
            use_vad=False,
            min_silence_ms=500,
            word_timestamps=False,
            prompt_context=compiled_vi.text,
        )

        self.service.transcribe_batch(request_vi, self.batch, lambda: False)
        passed_prompt = self.fake_model.kwargs.get("initial_prompt", "")
        self.assertIn("Tiền bối, Hậu bối, Senpai, Kouhai, Tớ, Cậu, Biến hình, Phép thuật, Quái vật", passed_prompt)

    def test_tier1_scenario_b_japanese_language_biases_kanji_school_honorifics(self):
        """Kịch bản B (bản tiếng Nhật): video_language='ja' nạp đúng 先輩, 後輩, お姉さま, 先生 lên top."""
        summary = "プリキュアと先輩・後輩たちが変身して妖魔と戦う"
        terms_ja = extract_glossary_offline(summary, video_language="ja")

        # Top 4 terms must be Japanese school honorifics
        self.assertEqual(terms_ja[:4], ["先輩", "後輩", "お姉さま", "先生"])

        context_ja = TranscriptionContext(context=summary, glossary=terms_ja)
        compiled_ja = self.prompt_builder.build(context_ja)

        self.assertTrue(compiled_ja.text.startswith("Terminology: 先輩, 後輩, お姉さま, 先生"))

        request_ja = SubtitleGenerationRequest(
            request_id="req_b_ja",
            project_id="proj_b",
            source_fingerprint="fp_b",
            video_path="audio_clip.mp4",
            model_size="tiny",
            compute_type="int8",
            language="ja",
            use_vad=False,
            min_silence_ms=500,
            word_timestamps=False,
            prompt_context=compiled_ja.text,
        )

        self.service.transcribe_batch(request_ja, self.batch, lambda: False)
        passed_prompt = self.fake_model.kwargs.get("initial_prompt", "")
        self.assertIn("先輩, 後輩, お姉さま, 先生", passed_prompt)

    def test_tier1_budget_pressure_never_truncates_top_honorifics(self):
        """Khi danh sách từ mồi quá dài, phần đuôi bị cắt nhưng top honorifics không bao giờ bị cắt."""
        summary = "Precure cùng các tiền bối và hậu bối biến hình chiến đấu tiêu diệt quái vật"
        terms = extract_glossary_offline(summary, video_language="vi")

        # Giả lập danh sách thêm 40 từ chuyên ngành phía sau
        extended_terms = terms + [f"ExtraTerm{i}" for i in range(40)]
        context = TranscriptionContext(context="Rất dài " * 30, glossary=extended_terms)

        # Giới hạn token chặt chẽ (25 tokens)
        compiled = self.prompt_builder.build(context, max_tokens=25)

        # Phía sau bị cắt bỏ (truncated = True)
        self.assertTrue(compiled.truncated)
        self.assertGreater(compiled.glossary_items_dropped, 0)

        # Nhưng chuỗi top honorifics vẫn nằm trọn vẹn ở đầu prompt
        self.assertIn("Terminology: Tiền bối, Hậu bối, Senpai, Kouhai", compiled.text)

    # =========================================================================
    # Acceptance Criterion 3 & Tier 2: Audio Inference A/B Test
    # =========================================================================
    def test_tier2_audio_inference_ab_homophone_vs_prompt_biased(self):
        """
        Tầng 2: So sánh kết quả nhận diện âm thanh mẫu 3-5s:
        - KHÔNG có Glossary: Whisper nhận diện tự do -> từ đồng âm sai 'Zenpai, tasukete!'
        - CÓ Glossary: Prompt biasing bắt dính 100% -> '先輩、助けて！'
        """
        inference_engine = BiasedWhisperInferenceEngine()
        self.service.model = inference_engine

        # Kịch bản A: Tắt Glossary (No summary)
        req_a = SubtitleGenerationRequest(
            request_id="req_inf_a",
            project_id="p_a",
            source_fingerprint="fp_a",
            video_path="audio_senpai_tasukete.wav",
            model_size="tiny",
            compute_type="int8",
            language="ja",
            use_vad=False,
            min_silence_ms=500,
            word_timestamps=False,
            prompt_context="",
        )
        result_a = self.service.transcribe_batch(req_a, self.batch, lambda: False)
        text_a = result_a.segments[0].text if result_a.segments else ""

        # Không có glossary: bị sai chính tả/đồng âm
        self.assertEqual(text_a, "Zenpai, tasukete!")
        self.assertNotIn("先輩", text_a)

        # Kịch bản B: Bật Glossary (With summary)
        summary = "プリキュアと先輩・後輩たちが変身して妖魔と戦う"
        terms = extract_glossary_offline(summary, video_language="ja")
        compiled = self.prompt_builder.build(TranscriptionContext(context=summary, glossary=terms))

        req_b = SubtitleGenerationRequest(
            request_id="req_inf_b",
            project_id="p_b",
            source_fingerprint="fp_b",
            video_path="audio_senpai_tasukete.wav",
            model_size="tiny",
            compute_type="int8",
            language="ja",
            use_vad=False,
            min_silence_ms=500,
            word_timestamps=False,
            prompt_context=compiled.text,
        )
        result_b = self.service.transcribe_batch(req_b, self.batch, lambda: False)
        text_b = result_b.segments[0].text if result_b.segments else ""

        # Có glossary: bắt dính 100% đúng từ khóa chuẩn
        self.assertEqual(text_b, "先輩、助けて！")
        self.assertIn("先輩", text_b)


if __name__ == "__main__":
    unittest.main()
