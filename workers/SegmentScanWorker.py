from PySide6.QtCore import QThread, Signal
from core.subtitle_generation.faster_whisper_service import FasterWhisperService
from core.subtitle_generation.subtitle_generation_request import SubtitleGenerationRequest
from core.subtitle_generation.subtitle_generation_batch import SubtitleGenerationBatch
import datetime

class SegmentScanWorker(QThread):
    """
    Worker dng d? chay lai Speech Recognition (Whisper) cho 1 doan subtitle
    d duoc thay doi thoi gian tren Timeline, m khng lm ?nh huong den
    cc ti?n trnh khc ho?c thay doi ID cua subtitle.
    """
    finished_signal = Signal(str, str) # segment_id, new_text
    error_signal = Signal(str, str) # segment_id, error_msg

    def __init__(
        self,
        segment_id: str,
        start_ms: int,
        end_ms: int,
        request: SubtitleGenerationRequest,
        whisper_service: FasterWhisperService,
    ):
        super().__init__()
        self.segment_id = segment_id
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.request = request
        self.whisper_service = whisper_service
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self._is_cancelled:
                return

            # T?i model v?i thi?t l?p t? request
            self.whisper_service.load_model(self.request.model_size, self.request.compute_type)
            
            now_iso = datetime.datetime.now().isoformat()
            # T?o 1 batch gi? l?p cho do?n m thanh ny
            batch = SubtitleGenerationBatch(
                batch_id="scan_" + str(self.segment_id),
                start_ms=self.start_ms,
                end_ms=self.end_ms,
                status="RUNNING",
                revision=1,
                created_at=now_iso,
                updated_at=now_iso
            )

            # Ch?y transcribe b?ng api c? s? d? l?y audio clip & ch?y AI
            result = self.whisper_service.transcribe_batch(
                self.request, batch, lambda: self._is_cancelled
            )

            if self._is_cancelled:
                return

            if result.error:
                self.error_signal.emit(self.segment_id, result.error)
            else:
                # N?i v?n b?n t? c?c phn do?n tr? v? (th??ng l 1 ho?c vi cu)
                text = " ".join([seg.text.strip() for seg in result.segments])
                if not text:
                    text = "[Không nhận diện được giọng nói]"
                self.finished_signal.emit(self.segment_id, text)
                
        except Exception as e:
            self.error_signal.emit(self.segment_id, str(e))
