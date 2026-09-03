import os
import shutil
import subprocess
import tempfile
from typing import Callable, Optional, Tuple

from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from core.subtitle_generation.subtitle_generation_result import (
    SubtitleGenerationResult,
    WhisperSegmentResult,
)
from core.runtime.runtime_paths import RuntimePaths
from core.services.model_manager import ModelManager


class FasterWhisperService:
    """Thin ASR adapter: inference in, segment objects out; no artifact I/O."""

    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None
        self.current_model_size: Optional[str] = None
        self.current_compute_type: Optional[str] = None

    def load_model(self, model_size: str, compute_type: str) -> None:
        if (
            self.model is not None
            and self.current_model_size == model_size
            and self.current_compute_type == compute_type
        ):
            return

        self.unload_model()
        try:
            from faster_whisper import WhisperModel

            model_path = ModelManager.get_model_path_for_inference(model_size)
            self.model = WhisperModel(
                model_path,
                device=self.device,
                compute_type=compute_type,
                download_root=str(RuntimePaths.get_models_dir()),
            )
            self.current_model_size = model_size
            self.current_compute_type = compute_type
        except Exception as exc:
            raise RuntimeError(f"Failed to load Faster-Whisper model: {exc}") from exc

    def unload_model(self) -> None:
        self.model = None
        self.current_model_size = None
        self.current_compute_type = None

    def transcribe_batch(
        self,
        request: SubtitleGenerationRequest,
        batch: SubtitleGenerationBatch,
        is_cancelled: Callable[[], bool],
    ) -> SubtitleGenerationResult:
        if self.model is None:
            return SubtitleGenerationResult(
                batch_id=batch.batch_id,
                segments=[],
                error="Faster-Whisper model is not loaded.",
            )
        if batch.start_ms < 0 or batch.end_ms <= batch.start_ms:
            return SubtitleGenerationResult(
                batch_id=batch.batch_id,
                segments=[],
                error="Invalid batch time range.",
            )
        if is_cancelled():
            return SubtitleGenerationResult(batch.batch_id, [], "Cancelled.")

        temp_dir = None
        try:
            transcribe_options = {
                "language": request.language,
                "beam_size": 5,
                "word_timestamps": request.word_timestamps,
            }
            if request.prompt_context.strip():
                transcribe_options["initial_prompt"] = request.prompt_context
            # Every batch is an independent, zero-based audio input.  This
            # keeps VAD compatible with batch processing and makes the offset
            # contract unambiguous for both VAD and non-VAD transcription.
            input_path, temp_dir = self._extract_batch_audio(request, batch)
            timestamp_offset_ms = batch.start_ms
            if request.use_vad:
                transcribe_options["vad_filter"] = True
                transcribe_options["vad_parameters"] = {
                    "min_silence_duration_ms": request.min_silence_ms
                }
            else:
                transcribe_options["vad_filter"] = False

            segments, _info = self.model.transcribe(
                input_path, **transcribe_options
            )
            results = []
            for segment in segments:
                if is_cancelled():
                    return SubtitleGenerationResult(batch.batch_id, [], "Cancelled.")

                words = None
                if request.word_timestamps and getattr(segment, "words", None):
                    words = [
                        {
                            "word": word.word,
                            "start_ms": self._shift_ms(word.start, timestamp_offset_ms),
                            "end_ms": self._shift_ms(word.end, timestamp_offset_ms),
                        }
                        for word in segment.words
                        if word.start is not None and word.end is not None
                    ]
                    words = words or None

                results.append(
                    WhisperSegmentResult(
                        start_ms=self._shift_ms(segment.start, timestamp_offset_ms),
                        end_ms=self._shift_ms(segment.end, timestamp_offset_ms),
                        text=segment.text.strip(),
                        words=words,
                    )
                )
            return SubtitleGenerationResult(batch.batch_id, results)
        except Exception as exc:
            return SubtitleGenerationResult(batch.batch_id, [], str(exc))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _extract_batch_audio(
        request: SubtitleGenerationRequest, batch: SubtitleGenerationBatch
    ) -> Tuple[str, str]:
        """Crop one batch to a temporary 16 kHz mono WAV for VAD + ASR."""
        temp_dir = tempfile.mkdtemp(prefix="subtitle_generation_batch_")
        output_path = os.path.join(temp_dir, "audio.wav")
        duration_s = (batch.end_ms - batch.start_ms) / 1000
        command = [
            RuntimePaths.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            request.video_path,
            # Output seeking is deliberately used here: input seeking can
            # begin at a preceding keyframe, which breaks the zero-based
            # timestamp contract for the extracted WAV.
            "-ss",
            f"{batch.start_ms / 1000:.3f}",
            "-t",
            f"{duration_s:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-y",
            output_path,
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to extract audio batch: {exc}") from exc
        return output_path, temp_dir

    @staticmethod
    def _shift_ms(seconds: float, offset_ms: int) -> int:
        return max(0, int(round(seconds * 1000)) + offset_ms)
