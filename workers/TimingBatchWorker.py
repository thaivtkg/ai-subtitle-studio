import os
import tempfile
import subprocess
import traceback
from PySide6.QtCore import QThread, Signal

from core.timing.timing_run_request import TimingRunRequest

class TimingBatchWorker(QThread):
    """
    [S7.1-T09] TimingBatchWorker: Cỗ máy thực thi AI theo khối (Batch)
    Cô lập hoàn toàn khỏi UI và Project State. Chỉ nhận Request và trả về Segments.
    """
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    
    # finished_signal(list_of_segments, is_end_of_source)
    finished_signal = Signal(list, bool) 
    error_signal = Signal(str)

    def __init__(self, request: TimingRunRequest):
        super().__init__()
        self.request = request
        self.is_cancelled = False

    def run(self):
        chunk_wav = None
        try:
            # 1. [S7.1-T11] Tính toán Boundary Overlap
            # Lùi lại `overlap_ms` để bắt trọn câu nói lỡ bị cắt ngang giữa 2 batch
            overlap = self.request.overlap_ms if self.request.start_ms > 0 else 0
            actual_start_ms = max(0, self.request.start_ms - overlap)
            
            start_sec = actual_start_ms / 1000.0
            duration_sec = self.request.max_window_ms / 1000.0

            self.log_signal.emit(f"[Batch Worker] Trích xuất audio từ {start_sec:.2f}s, window tối đa {duration_sec}s...")

            # 2. [S7.1-T10] Time-Range Execution (Cắt Audio siêu tốc)
            temp_dir = tempfile.gettempdir()
            chunk_wav = os.path.join(temp_dir, f"timing_chunk_{id(self)}.wav")
            
            # Lệnh FFmpeg chỉ trích xuất đúng khung thời gian mong muốn, tiết kiệm RAM tuyệt đối
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_sec),
                "-t", str(duration_sec),
                "-i", self.request.video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                chunk_wav
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            process.communicate()

            if self.is_cancelled:
                return

            if not os.path.exists(chunk_wav) or os.path.getsize(chunk_wav) < 1024:
                self.log_signal.emit("[Batch Worker] Trích xuất trả về rỗng (Đã đến cuối video).")
                self.finished_signal.emit([], True)
                return

            # 3. Chạy Faster-Whisper trên phân đoạn Audio
            from faster_whisper import WhisperModel
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = self.request.compute_type if device == "cuda" else "int8"
            
            self.log_signal.emit(f"[Batch Worker] Đang tải Model Whisper ({self.request.model_size})...")
            model = WhisperModel(self.request.model_size, device=device, compute_type=compute_type)
            
            self.log_signal.emit("[Batch Worker] Đang nhận diện (Infer) âm thanh...")
            
            vad_filter = self.request.use_vad
            vad_parameters = dict(min_silence_duration_ms=self.request.min_silence_ms) if vad_filter else None
            
            segments_generator, info = model.transcribe(
                chunk_wav,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters,
                word_timestamps=False
            )

            # Đánh giá xem window này đã chạm tới cuối file video gốc chưa
            is_end_of_source = info.duration < (duration_sec - 1.0)

            raw_segments = []
            for seg in segments_generator:
                if self.is_cancelled:
                    return
                raw_segments.append(seg)
                self.progress_signal.emit(50, f"Đang nhận diện: {seg.end:.1f}s / {info.duration:.1f}s")
                
                # Tối ưu: Nếu số lượng đoạn lấy được vượt quá 1.5 lần số yêu cầu -> Dừng sớm
                if len(raw_segments) > self.request.target_segment_count * 1.5:
                    break

            # 4. [S7.1-T12] Dedupe & Tính toán hệ quy chiếu thời gian gốc
            final_segments = []
            for seg in raw_segments:
                abs_start_ms = int(seg.start * 1000) + actual_start_ms
                abs_end_ms = int(seg.end * 1000) + actual_start_ms
                
                # [S7.1-FIX] Deduplication dựa trên Điểm kết thúc (End-Boundary)
                # Nếu câu này kết thúc trước hoặc loanh quanh điểm nối (sai số 250ms), 
                # nó chắc chắn là câu của Batch trước lọt vào vùng Overlap nên ta bỏ qua.
                # Ngược lại, nếu nó lấn sâu sang vùng thời gian mới, đó là câu mới.
                if abs_end_ms <= self.request.start_ms + 250 and self.request.start_ms > 0:
                    continue
                    
                # Do đây là luồng "Timing Draft", AI không cần điền Text vào phụ đề. 
                final_segments.append({
                    "start_ms": abs_start_ms,
                    "end_ms": abs_end_ms,
                    "text": ""
                })  

            # 5. [S7.1-T13] Giới hạn số lượng (Partial Result Isolation)
            if len(final_segments) > self.request.target_segment_count:
                final_segments = final_segments[:self.request.target_segment_count]
                # Nếu cắt bớt segment, chắc chắn chưa phải là cuối source
                is_end_of_source = False 

            self.progress_signal.emit(100, "Hoàn tất Chunk.")
            self.finished_signal.emit(final_segments, is_end_of_source)

        except Exception as e:
            self.error_signal.emit(str(e))
            print(traceback.format_exc())
            
        finally:
            # Dọn dẹp chunk audio tạm
            if chunk_wav and os.path.exists(chunk_wav):
                try:
                    os.remove(chunk_wav)
                except:
                    pass

    def cancel(self):
        self.is_cancelled = True