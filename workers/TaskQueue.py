import os
import re
import time
import subprocess
import psutil

try:
    import GPUtil
except ImportError:
    GPUtil = None

from PySide6.QtCore import QThread, Signal
from utils import resource_path
from core.output_path_service import OutputPathService

# ==========================================
# CÁC HÀM TIỆN ÍCH DÙNG CHUNG (HELPER FUNCTIONS)
# ==========================================
def format_eta(seconds):
    if seconds < 0 or seconds > 86400: return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_hardware_stats():
    cpu = psutil.cpu_percent(interval=None)
    gpu = 0
    if GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            if gpus: gpu = gpus[0].load * 100
        except Exception:
            pass
    return f"CPU: {cpu:.0f}% | GPU: {gpu:.0f}%"

def get_video_duration(video_path):
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

def has_audio_stream(video_path):
    ffprobe_path = resource_path(os.path.join("bin", "ffprobe.exe"))
    try:
        cmd = [ffprobe_path, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return "audio" in res.stdout.lower()
    except Exception:
        return True 

# ==========================================
# 1. WHISPER WORKER (CHUYÊN TRÁCH TẠO SRT)
# ==========================================
class WhisperWorker(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(str, str)
    error_signal = Signal(str)

    def __init__(self, video_path, output_dir, initial_prompt, compute_type, use_vad, min_silence_ms, model_size="large-v3-turbo", generation_mode="full"):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.initial_prompt = initial_prompt
        self.compute_type = compute_type
        self.use_vad = use_vad
        self.min_silence_ms = min_silence_ms
        self.model_size = model_size
        self.generation_mode = generation_mode # [P2-T2] Biến lưu chế độ chạy
        self._is_cancelled = False
        
        self.actual_srt_path = None 

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            psutil.cpu_percent(interval=0.1)
            
            if not has_audio_stream(self.video_path):
                self.error_signal.emit("Video không có luồng âm thanh (No Audio). Không thể nhận diện phụ đề.")
                return

            video_duration = get_video_duration(self.video_path)
            self.log_signal.emit(f"[AI] Đang nhận diện âm thanh và khởi động mô hình...")
            
            from core.Backend import generate_srt, generate_timing_draft
            
            # Cấp phát đường dẫn tạm thời (Sẽ được ghi đè chính xác từ Log của Backend)
            ext = "_timing.srt" if self.generation_mode == "timing" else ".srt"
            target_srt = OutputPathService.build_subtitle_path(self.output_dir, self.video_path, ext)
            self.actual_srt_path = target_srt 
            target_dir = os.path.dirname(target_srt)
            
            whisper_start_time = time.time()

            def whisper_progress(p, msg):
                overall_p = min(100, int(p))
                stats_str = ""
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

                self.progress_signal.emit(overall_p, f"Đang xử lý...{stats_str}")
                
                # [FIX BLOCKER] Bắt (Hook) chính xác đường dẫn file được Backend xuất ra
                if "tại:" in msg:
                    extracted_path = msg.split("tại:")[-1].strip()
                    self.actual_srt_path = extracted_path.replace('\\', '/') 
                
                if msg and "Đang" not in msg and "Processing" not in msg and "Hoàn tất" not in msg:
                    self.log_signal.emit(f"[Sub] ➜ {msg}")

            # [P2-T2] Rẽ nhánh tùy theo chế độ được yêu cầu từ UI
            if self.generation_mode == "timing":
                generate_timing_draft(
                    video_path=self.video_path,
                    output_dir=target_dir,
                    model_size=self.model_size,
                    compute_type=self.compute_type,
                    use_vad=self.use_vad,
                    min_silence_ms=self.min_silence_ms,
                    progress_callback=whisper_progress,
                    cancel_check=lambda: self._is_cancelled, 
                    video_duration=video_duration
                )
            else:
                generate_srt(
                    video_path=self.video_path,
                    output_dir=target_dir,
                    model_size=self.model_size,
                    compute_type=self.compute_type,
                    initial_prompt=self.initial_prompt,
                    use_vad=self.use_vad,
                    min_silence_ms=self.min_silence_ms,
                    progress_callback=whisper_progress,
                    cancel_check=lambda: self._is_cancelled, 
                    video_duration=video_duration
                )
            
            if not self._is_cancelled:
                mode_name = "Timing Draft" if self.generation_mode == "timing" else "Subtitle"
                self.progress_signal.emit(100, f"Tạo {mode_name} hoàn tất!")
                self.finished_signal.emit("Thành công", self.actual_srt_path)
            else:
                self.error_signal.emit("Đã hủy tiến trình AI.")
                
        except Exception as e:
            if self._is_cancelled:
                self.error_signal.emit("Đã hủy tiến trình.")
            else:
                self.error_signal.emit(f"Lỗi AI: {str(e)}")


# ==========================================
# 2. HARDSUB WORKER (CHUYÊN TRÁCH RENDER FFMPEG)
# ==========================================
class HardsubWorker(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(str, str)
    error_signal = Signal(str)

    def __init__(self, video_path, srt_path, output_dir, font_size, font_color, font_name):
        super().__init__()
        self.video_path = video_path
        self.srt_path = srt_path
        self.output_dir = output_dir
        self.font_size = font_size
        self.font_color = font_color
        self.font_name = font_name
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

    def run(self):
        try:
            psutil.cpu_percent(interval=0.1)
            video_duration = get_video_duration(self.video_path)
            
            # 1. Cấp phát đường dẫn Output chuẩn từ Service
            out_video_path = OutputPathService.build_hardsub_path(self.output_dir, self.video_path, ".mp4")
            
            # [HOTFIX BLOCKER] Bắt buộc khởi tạo thư mục Output trước khi FFmpeg chạm vào
            # Nếu bỏ qua bước này, FFmpeg sẽ văng lỗi Invalid Argument vì không tìm thấy folder
            os.makedirs(os.path.dirname(out_video_path), exist_ok=True)

            # [FIX FFMPEG] Làm sạch hoàn toàn đường dẫn: Chỉ dùng Dấu gạch chéo chuẩn (/)
            # Bỏ qua cơ chế TempFile và Escape dấu hai chấm (:) vì nó gây xung đột với Backend
            safe_srt_path = self.srt_path.replace('\\', '/')
            safe_video_path = self.video_path.replace('\\', '/')
            safe_out_path = out_video_path.replace('\\', '/')

            from core.Backend import burn_hardsub
            
            def hardsub_log_handler(msg):
                self.log_signal.emit(msg)
                time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", msg)
                speed_match = re.search(r"speed=\s*([\d\.]+)x", msg)
                
                if time_match and video_duration > 0:
                    h, m, s = map(float, time_match.groups())
                    current_sec = h * 3600 + m * 60 + s
                    ff_percent = min(100, (current_sec / video_duration) * 100)
                    
                    stats_str = ""
                    if speed_match:
                        speed = float(speed_match.group(1))
                        if speed > 0:
                            remain_sec = (video_duration - current_sec) / speed
                            hw = get_hardware_stats()
                            stats_str = f" ({speed:.1f}x | Còn: {format_eta(remain_sec)} | {hw})"

                    self.progress_signal.emit(int(ff_percent), f"Đang Burn Hardsub: {int(ff_percent)}%{stats_str}")
                elif time_match:
                    self.progress_signal.emit(0, "Đang Burn Hardsub... (Đang tính toán)")

            burn_hardsub(
                video_path=safe_video_path,
                srt_path=safe_srt_path, # Truyền đường dẫn sạch bóng vào Backend
                output_path=safe_out_path,
                font_size=self.font_size,
                font_color=self.font_color,
                font_name=self.font_name,
                progress_callback=None,
                log_callback=hardsub_log_handler,
                process_callback=lambda proc: setattr(self, 'current_process', proc)
            )

            if not self._is_cancelled:
                self.progress_signal.emit(100, "Burn Hardsub hoàn tất!")
                self.finished_signal.emit("Thành công", safe_out_path)
            else:
                self.error_signal.emit("Đã hủy tiến trình FFmpeg.")

        except Exception as e:
            if self._is_cancelled:
                self.error_signal.emit("Đã hủy tiến trình.")
            else:
                self.error_signal.emit(f"Lỗi Render: {str(e)}")

# ==========================================
# 3. FILL TEXT WORKER (P2-T9: ĐIỀN CHỮ VÀO TIMING DRAFT)
# ==========================================
class FillTextWorker(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(list) # Trả về list các segment đã điền chữ
    error_signal = Signal(str)

    def __init__(self, video_path, segments_data, initial_prompt, compute_type, model_size="large-v3-turbo"):
        super().__init__()
        self.video_path = video_path
        self.segments_data = segments_data
        self.initial_prompt = initial_prompt
        self.compute_type = compute_type
        self.model_size = model_size
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            from core.Backend import fill_text_for_segments
            
            self.log_signal.emit(f"[AI] Bắt đầu điền chữ cho {len(self.segments_data)} mốc thời gian...")
            
            result = fill_text_for_segments(
                video_path=self.video_path,
                segments_data=self.segments_data,
                model_size=self.model_size,
                compute_type=self.compute_type,
                initial_prompt=self.initial_prompt,
                progress_callback=lambda p, msg: self.progress_signal.emit(p, msg),
                cancel_check=lambda: self._is_cancelled
            )
            
            if not self._is_cancelled:
                self.progress_signal.emit(100, "Điền chữ hoàn tất!")
                self.finished_signal.emit(result)
            else:
                self.error_signal.emit("Đã hủy tiến trình điền chữ.")
        except Exception as e:
            if self._is_cancelled:
                self.error_signal.emit("Đã hủy tiến trình.")
            else:
                self.error_signal.emit(f"Lỗi AI: {str(e)}")