import os
import sys
import shutil
from pathlib import Path

class RuntimePaths:
    """[S7.2-T05] Quản lý toàn bộ đường dẫn của ứng dụng (Dev & PyInstaller Release)"""
    APP_NAME = "AI Subtitle Studio"

    @staticmethod
    def get_app_dir() -> Path:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parent.parent.parent

    # --- HỆ THỐNG BINARY GÓI KÈM (TỰ ĐỘNG DÒ TÌM & FALLBACK) ---
    @staticmethod
    def get_ffmpeg_dir() -> Path:
        return RuntimePaths.get_app_dir() / "ffmpeg"

    @staticmethod
    def get_ffmpeg_exe() -> str:
        candidates = [
            RuntimePaths.get_ffmpeg_dir() / "ffmpeg.exe",
            RuntimePaths.get_ffmpeg_dir() / "bin" / "ffmpeg.exe",
            RuntimePaths.get_app_dir() / "bin" / "ffmpeg.exe",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        
        # Fallback tìm trong biến môi trường PATH của hệ điều hành
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
            
        return str(candidates[0])

    @staticmethod
    def get_ffprobe_exe() -> str:
        candidates = [
            RuntimePaths.get_ffmpeg_dir() / "ffprobe.exe",
            RuntimePaths.get_ffmpeg_dir() / "bin" / "ffprobe.exe",
            RuntimePaths.get_app_dir() / "bin" / "ffprobe.exe",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
                
        system_ffprobe = shutil.which("ffprobe")
        if system_ffprobe:
            return system_ffprobe
            
        return str(candidates[0])

    @staticmethod
    def get_resources_dir() -> Path:
        return RuntimePaths.get_app_dir() / "resources"

    # --- DỮ LIỆU NGƯỜI DÙNG (READ/WRITE LOCALAPPDATA) ---
    @staticmethod
    def get_user_data_dir() -> Path:
        local_app_data = os.environ.get('LOCALAPPDATA')
        if not local_app_data:
            local_app_data = os.path.expanduser('~')
        data_dir = Path(local_app_data) / RuntimePaths.APP_NAME
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def get_models_dir() -> Path:
        path = RuntimePaths.get_user_data_dir() / "models"
        path.mkdir(exist_ok=True)
        return path

    @staticmethod
    def get_logs_dir() -> Path:
        path = RuntimePaths.get_user_data_dir() / "logs"
        path.mkdir(exist_ok=True)
        return path

    @staticmethod
    def get_settings_file() -> Path:
        return RuntimePaths.get_user_data_dir() / "settings.json"