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
    from core.runtime.runtime_paths import RuntimePaths
    ffprobe_path = RuntimePaths.get_ffprobe_exe()
    ffmpeg_path = RuntimePaths.get_ffmpeg_exe()
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

# ==========================================
# 1. HARDSUB WORKER (CHUYÊN TRÁCH RENDER FFMPEG)
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
