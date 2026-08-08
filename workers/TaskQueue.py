import os
import re
import json
import subprocess
import time
import psutil
try:
    import GPUtil
except ImportError:
    GPUtil = None

from PySide6.QtCore import QThread, Signal
from utils import resource_path

# Hàm định dạng số giây thành HH:MM:SS
def format_eta(seconds):
    if seconds < 0 or seconds > 86400: return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

# Hàm lấy thông số CPU / GPU
def get_hardware_stats():
    cpu = psutil.cpu_percent(interval=None)
    gpu = 0
    if GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0].load * 100
        except Exception:
            pass
    return f"CPU: {cpu:.0f}% | GPU: {gpu:.0f}%"

class AdvancedWorkerThread(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, tasks, output_dir, initial_prompt, min_silence_len, do_hardsub, font_size, font_color, font_name, compute_type, use_vad, min_silence_ms,model_size="large-v3-turbo"):
        super().__init__()
        self.tasks = tasks
        self.output_dir = output_dir
        self.initial_prompt = initial_prompt
        self.min_silence_len = min_silence_len
        self.do_hardsub = do_hardsub
        self.font_size = font_size
        self.font_color = font_color
        self.font_name = font_name
        self.compute_type = compute_type
        self.use_vad = use_vad
        self.min_silence_ms = min_silence_ms
        self.model_size = model_size
        self._is_cancelled = False
        self.current_process = None

    def cancel(self):
        self._is_cancelled = True
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.kill()
            except Exception:
                pass

    def get_video_duration(self, video_path):

        ffprobe_path = resource_path(os.path.join("bin", "ffprobe.exe"))
        ffmpeg_path = resource_path(os.path.join("bin", "ffmpeg.exe"))

        try:
            cmd = [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            duration = float(res.stdout.strip())
            if duration > 0: return duration
        except Exception:
            pass
            
        try:
            cmd = [ffmpeg_path, "-i", video_path]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d{2,})", res.stderr)
            if match:
                h, m, s = map(float, match.groups())
                return h * 3600 + m * 60 + s
        except Exception:
            pass
            
        return 0.0 

    def run(self):
        try:
            total_tasks = len(self.tasks)
            # Kích hoạt thử psutil để các lần gọi sau chính xác hơn
            psutil.cpu_percent(interval=0.1)

            for idx, (video_path, srt_path) in enumerate(self.tasks):
                if self._is_cancelled: break
                
                file_name = os.path.basename(video_path)
                self.log_signal.emit(f"\n--- Đang xử lý [{idx+1}/{total_tasks}]: {file_name} ---")
                
                video_duration = self.get_video_duration(video_path)
                weight_ai = 0.5 if self.do_hardsub else 1.0

                # 1. BƯỚC TẠO SRT (AI WHISPER)
                if not srt_path:
                    self.log_signal.emit(f"[AI] Đang chạy Whisper nhận diện giọng nói...")
                    self.log_signal.emit(f"[AI] Đang nhận diện ngôn ngữ...")
                    from core.Backend import generate_srt
                    
                    base_name = os.path.splitext(file_name)[0]
                    target_srt = os.path.join(self.output_dir if self.output_dir else os.path.dirname(video_path), f"{base_name}.srt")
                    
                    whisper_start_time = time.time()

                    def whisper_progress(p, msg):
                        base_p = int((idx / total_tasks) * 100)
                        file_p = int((p * weight_ai) / total_tasks)
                        overall_p = min(100, base_p + file_p)
                        
                        stats_str = ""
                        # Trích xuất timestamp từ log để tính tốc độ
                        time_match = re.search(r"\[(\d{2}):(\d{2}):(\d{2}),(\d{3})\]", msg)
                        if time_match and video_duration > 0:
                            h, m, s, ms = map(int, time_match.groups())
                            current_audio_sec = h * 3600 + m * 60 + s + ms / 1000.0
                            elapsed = time.time() - whisper_start_time
                            
                            if elapsed > 0 and current_audio_sec > 0:
                                speed = current_audio_sec / elapsed
                                remain_sec = (video_duration - current_audio_sec) / speed
                                hw = get_hardware_stats()
                                stats_str = f" ({speed:.1f}x | Còn: {format_eta(remain_sec)} | {hw})"

                        self.progress_signal.emit(overall_p, f"Đang tạo Subtitle...{stats_str}")
                        
                        if msg and "Đang" not in msg and "Processing" not in msg and "Hoàn tất" not in msg:
                            self.log_signal.emit(f"[Sub] ➜ {msg}")

                    generate_srt(
                        video_path=video_path,
                        output_dir=os.path.dirname(target_srt),
                        model_size=self.model_size, # ĐÃ CHUYỂN SANG TURBO
                        compute_type=self.compute_type,
                        initial_prompt=self.initial_prompt,
                        use_vad=self.use_vad,
                        min_silence_ms=self.min_silence_ms,
                        progress_callback=whisper_progress,
                        cancel_check=lambda: self._is_cancelled, 
                        video_duration=video_duration
                    )
                    srt_path = target_srt

                # 2. BƯỚC CHÈN HARDSUB (FFMPEG)
                if self.do_hardsub:
                    if self._is_cancelled: break
                    self.log_signal.emit(f"[FFmpeg] Chuẩn bị khởi chạy tiến trình chèn hardsub...")
                    
                    out_dir = self.output_dir if self.output_dir else os.path.dirname(video_path)
                    out_video_path = os.path.join(out_dir, f"hardsub_{file_name}")

                    from core.Backend import burn_hardsub
                    
                    def hardsub_log_handler(msg):
                        self.log_signal.emit(msg)
                        
                        time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", msg)
                        speed_match = re.search(r"speed=\s*([\d\.]+)x", msg)
                        
                        if time_match and video_duration > 0:
                            h, m, s = map(float, time_match.groups())
                            current_sec = h * 3600 + m * 60 + s
                            ff_percent = min(100, (current_sec / video_duration) * 100)
                            
                            overall_p = int((idx / total_tasks) * 100 + (50 / total_tasks) + (ff_percent * 0.5 / total_tasks))
                            
                            stats_str = ""
                            if speed_match:
                                speed = float(speed_match.group(1))
                                if speed > 0:
                                    remain_sec = (video_duration - current_sec) / speed
                                    hw = get_hardware_stats()
                                    stats_str = f" ({speed:.1f}x | Còn: {format_eta(remain_sec)} | {hw})"

                            self.progress_signal.emit(overall_p, f"Đang Burn Hardsub: {int(ff_percent)}%{stats_str}")
                        elif time_match:
                            overall_p = int((idx / total_tasks) * 100 + (50 / total_tasks))
                            self.progress_signal.emit(overall_p, "Đang Burn Hardsub... (Đang tính toán)")

                    burn_hardsub(
                        video_path=video_path,
                        srt_path=srt_path,
                        output_path=out_video_path,
                        font_size=self.font_size,
                        font_color=self.font_color,
                        font_name=self.font_name,
                        progress_callback=None,
                        log_callback=hardsub_log_handler,
                        process_callback=lambda proc: setattr(self, 'current_process', proc)
                    )

            if not self._is_cancelled:
                self.progress_signal.emit(100, "Hoàn tất!")
                self.finished_signal.emit("Tất cả tiến trình đã xử lý xong!")
            else:
                self.finished_signal.emit("Tiến trình đã bị hủy bởi người dùng.")

        except InterruptedError as ie:
            self.log_signal.emit(f"[HỆ THỐNG] {str(ie)}")
            self.finished_signal.emit("Tiến trình đã bị hủy bởi người dùng.")
        except Exception as e:
            if self._is_cancelled:
                self.log_signal.emit("[HỆ THỐNG] Đã buộc dừng tiến trình FFmpeg theo yêu cầu.")
                self.finished_signal.emit("Tiến trình đã bị hủy bởi người dùng.")
            else:
                self.error_signal.emit(str(e))