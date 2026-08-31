import os
import tempfile
import subprocess
import traceback
from PySide6.QtCore import QThread, Signal

from core.timing.timing_run_request import TimingRunRequest

class TimingBatchWorker(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(list, bool) 
    error_signal = Signal(str)

    def __init__(self, request: TimingRunRequest):
        super().__init__()
        self.request = request
        self.is_cancelled = False

    def _transcribe_with_vad_retry(self, model, chunk_wav):
        """Retry one empty VAD result at a lower, still-VAD threshold."""
        info = None
        for attempt, threshold in enumerate((0.5, 0.25), start=1):
            vad_parameters = {
                "min_silence_duration_ms": self.request.min_silence_ms,
                "threshold": threshold,
                "speech_pad_ms": 400,
            }
            segments_generator, info = model.transcribe(
                chunk_wav,
                vad_filter=True,
                vad_parameters=vad_parameters,
                word_timestamps=False,
            )
            raw_segments = list(segments_generator)
            duration = float(getattr(info, "duration", 0.0) or 0.0)
            duration_after_vad = float(
                getattr(info, "duration_after_vad", 0.0) or 0.0
            )
            language = getattr(info, "language", "?")
            probability = float(
                getattr(info, "language_probability", 0.0) or 0.0
            )
            self.log_signal.emit(
                "[Batch Worker] VAD "
                f"attempt={attempt}, threshold={threshold:.2f}, "
                f"audio={duration:.2f}s, speech={duration_after_vad:.2f}s, "
                f"language={language} ({probability:.2f}), "
                f"raw_segments={len(raw_segments)}."
            )
            if raw_segments or attempt == 2:
                return raw_segments, info
            self.log_signal.emit(
                "[Batch Worker] VAD trả về 0 segment; retry với threshold 0.25."
            )
        return [], info

    def run(self):
        chunk_wav = None
        try:
            from faster_whisper import WhisperModel
            import torch
            from core.runtime.runtime_paths import RuntimePaths
            from core.services.model_manager import ModelManager # <--- THÊM DOAN NÀY ĐỂ SỬ DỤNG ModelManager

            # [TỐI ƯU HÓA HIỆU NĂNG]
            # Chỉ nạp Whisper Model vào RAM/VRAM đúng 1 lần duy nhất cho toàn bộ Batch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = self.request.compute_type if device == "cuda" else "int8"
            
            self.log_signal.emit(f"[Batch Worker] Đang tải Model Whisper ({self.request.model_size})...")
            # [S7.2-T14] Ép Model Manager quyết định đường dẫn tải
            safe_model_path = ModelManager.get_model_path_for_inference(self.request.model_size)
            model = WhisperModel(
                safe_model_path, # <--- TRUYỀN ĐƯỜNG DẪN QUYẾT ĐỊNH VÀO ĐÂY
                device=device, 
                compute_type=compute_type,
                download_root=str(RuntimePaths.get_models_dir())
            )

            vad_filter = self.request.use_vad

            all_final_segments = []
            current_start_ms = self.request.start_ms
            is_end_of_source = False
            
            temp_dir = tempfile.gettempdir()
            chunk_wav = os.path.join(temp_dir, f"timing_chunk_{id(self)}.wav")

            # [S7.1-FIX-11] VÒNG LẶP TRƯỢT THỜI GIAN THÔNG MINH
            # Liên tục trượt cửa sổ thời gian cắt audio cho đến khi lấy đủ target_count
            while len(all_final_segments) < self.request.target_segment_count:
                if self.is_cancelled:
                    return

                overlap = self.request.overlap_ms if current_start_ms > 0 else 0
                actual_start_ms = max(0, current_start_ms - overlap)
                
                start_sec = actual_start_ms / 1000.0
                duration_sec = self.request.max_window_ms / 1000.0

                self.log_signal.emit(f"[Batch Worker] Trích xuất audio từ {start_sec:.2f}s, window {duration_sec}s...")

                cmd = [
                    RuntimePaths.get_ffmpeg_exe(), "-y",
                    "-ss", str(start_sec),
                    "-t", str(duration_sec),
                    "-i", self.request.video_path,
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    chunk_wav
                ]
                
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )

                stderr_lines = [
                    line.strip()
                    for line in (process.stderr or "").splitlines()
                    if any(
                        marker in line.casefold()
                        for marker in ("error", "invalid", "corrupt", "failed")
                    )
                ]
                chunk_size = (
                    os.path.getsize(chunk_wav) if os.path.exists(chunk_wav) else 0
                )
                self.log_signal.emit(
                    "[Batch Worker] FFmpeg "
                    f"exit={process.returncode}, wav_bytes={chunk_size}, "
                    f"decode_warnings={len(stderr_lines)}."
                )
                for line in stderr_lines[:3]:
                    self.log_signal.emit(f"[Batch Worker] FFmpeg warning: {line}")

                if process.returncode != 0:
                    detail = stderr_lines[-1] if stderr_lines else "unknown error"
                    raise RuntimeError(
                        f"FFmpeg không thể trích xuất audio (exit {process.returncode}): {detail}"
                    )

                if not os.path.exists(chunk_wav) or os.path.getsize(chunk_wav) < 1024:
                    self.log_signal.emit("[Batch Worker] Trích xuất trả về rỗng (Đã đến cuối video).")
                    is_end_of_source = True
                    break

                self.log_signal.emit("[Batch Worker] Đang nhận diện (Infer) âm thanh...")
                
                if vad_filter:
                    raw_segments, info = self._transcribe_with_vad_retry(
                        model, chunk_wav
                    )
                else:
                    segments_generator, info = model.transcribe(
                        chunk_wav,
                        vad_filter=False,
                        word_timestamps=False,
                    )
                    raw_segments = list(segments_generator)

                # Decoder warnings can shorten a nominal 120s WAV slightly.
                # Let the next extraction prove EOF instead of ending early.
                chunk_end_of_source = info.duration < (duration_sec - 5.0)

                for raw_index, seg in enumerate(raw_segments, start=1):
                    if self.is_cancelled:
                        return
                    prog = int((len(all_final_segments) + raw_index) / self.request.target_segment_count * 100)
                    self.progress_signal.emit(min(99, prog), f"Đã tìm thấy {len(all_final_segments) + raw_index}/{self.request.target_segment_count} câu...")

                added_in_chunk = 0
                last_end_ms_in_chunk = current_start_ms
                
                for seg in raw_segments:
                    abs_start_ms = int(seg.start * 1000) + actual_start_ms
                    abs_end_ms = int(seg.end * 1000) + actual_start_ms
                    
                    if abs_end_ms <= current_start_ms + 250 and current_start_ms > 0:
                        continue
                        
                    all_final_segments.append({
                        "start_ms": abs_start_ms,
                        "end_ms": abs_end_ms,
                        "text": ""
                    })
                    added_in_chunk += 1
                    last_end_ms_in_chunk = abs_end_ms

                    if len(all_final_segments) >= self.request.target_segment_count:
                        break

                if chunk_end_of_source and len(all_final_segments) < self.request.target_segment_count:
                    is_end_of_source = True
                    break
                    
                # Chống kẹt vòng lặp vô hạn ở những vùng video tĩnh lặng hoàn toàn
                if added_in_chunk == 0:
                    current_start_ms += int(info.duration * 1000) - self.request.overlap_ms
                else:
                    # Trượt cửa sổ tiến đến cuối câu phân tích vừa rồi
                    current_start_ms = last_end_ms_in_chunk

            if len(all_final_segments) > self.request.target_segment_count:
                all_final_segments = all_final_segments[:self.request.target_segment_count]
                is_end_of_source = False 

            self.progress_signal.emit(100, "Hoàn tất Batch.")
            self.finished_signal.emit(all_final_segments, is_end_of_source)

        except Exception as e:
            self.error_signal.emit(str(e))
            print(traceback.format_exc())
            
        finally:
            if chunk_wav and os.path.exists(chunk_wav):
                try:
                    os.remove(chunk_wav)
                except:
                    pass

    def cancel(self):
        self.is_cancelled = True
