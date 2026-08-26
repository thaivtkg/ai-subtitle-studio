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

    def run(self):
        chunk_wav = None
        try:
            from faster_whisper import WhisperModel
            import torch
            from core.runtime.runtime_paths import RuntimePaths

            # [TỐI ƯU HÓA HIỆU NĂNG]
            # Chỉ nạp Whisper Model vào RAM/VRAM đúng 1 lần duy nhất cho toàn bộ Batch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = self.request.compute_type if device == "cuda" else "int8"
            
            self.log_signal.emit(f"[Batch Worker] Đang tải Model Whisper ({self.request.model_size})...")
            model = WhisperModel(
                self.request.model_size, 
                device=device, 
                compute_type=compute_type,
                download_root=str(RuntimePaths.get_models_dir())
            )

            vad_filter = self.request.use_vad
            vad_parameters = dict(min_silence_duration_ms=self.request.min_silence_ms) if vad_filter else None

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
                
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                process.communicate()

                if not os.path.exists(chunk_wav) or os.path.getsize(chunk_wav) < 1024:
                    self.log_signal.emit("[Batch Worker] Trích xuất trả về rỗng (Đã đến cuối video).")
                    is_end_of_source = True
                    break

                self.log_signal.emit("[Batch Worker] Đang nhận diện (Infer) âm thanh...")
                
                segments_generator, info = model.transcribe(
                    chunk_wav,
                    vad_filter=vad_filter,
                    vad_parameters=vad_parameters,
                    word_timestamps=False
                )

                chunk_end_of_source = info.duration < (duration_sec - 1.0)
                raw_segments = []
                
                for seg in segments_generator:
                    if self.is_cancelled:
                        return
                    raw_segments.append(seg)
                    
                    prog = int((len(all_final_segments) + len(raw_segments)) / self.request.target_segment_count * 100)
                    self.progress_signal.emit(min(99, prog), f"Đã tìm thấy {len(all_final_segments) + len(raw_segments)}/{self.request.target_segment_count} câu...")
                    
                    if len(all_final_segments) + len(raw_segments) >= self.request.target_segment_count:
                        break 

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