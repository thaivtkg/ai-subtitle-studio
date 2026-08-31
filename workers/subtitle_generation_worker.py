from typing import Callable

from PySide6.QtCore import QThread, Signal

from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest


class SubtitleGenerationWorker(QThread):
    """Runs one batch only and returns data to the owner thread for validation/commit."""

    batch_success_signal = Signal(object, object)
    error_signal = Signal(str)

    def __init__(
        self,
        request: SubtitleGenerationRequest,
        batch: SubtitleGenerationBatch,
        whisper_service: FasterWhisperService,
    ):
        super().__init__()
        self.request = request
        self.batch = batch
        self.whisper_service = whisper_service
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            if self._is_cancelled:
                return
            result = self.whisper_service.transcribe_batch(
                self.request, self.batch, lambda: self._is_cancelled
            )
            if self._is_cancelled:
                return
            if result.error:
                self.error_signal.emit(
                    f"Batch {self.batch.batch_id} failed: {result.error}"
                )
                return
            self.batch_success_signal.emit(self.batch, result)
        except Exception as exc:
            self.error_signal.emit(f"Batch {self.batch.batch_id} failed: {exc}")
