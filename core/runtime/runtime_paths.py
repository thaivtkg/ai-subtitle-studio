import os
import sys
import shutil
from pathlib import Path

class RuntimePaths:
    """[S7.2-T05] Quản lý toàn bộ đường dẫn của ứng dụng (Dev & PyInstaller Release)"""
    APP_NAME = "AI Subtitle Studio"

    @staticmethod
    def get_app_dir() -> Path:
        """Thư mục chứa file thực thi (.exe) hoặc thư mục gốc mã nguồn (Dev)"""
        if getattr(sys, 'frozen', False):
            # Chạy file EXE đã đóng gói
            return Path(sys.executable).parent
        # Chạy từ mã nguồn (Dev)
        return Path(__file__).resolve().parent.parent.parent

    @staticmethod
    def get_internal_dir() -> Path:
        """Thư mục chứa tài nguyên nội bộ (_internal khi build onedir, root khi dev)"""
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return RuntimePaths.get_app_dir()

    # --- HỆ THỐNG BINARY GÓI KÈM (READ-ONLY) ---
    @staticmethod
    def get_ffmpeg_dir() -> Path:
        # Trong PyInstaller, FFmpeg sẽ nằm ở _internal/ffmpeg/
        return RuntimePaths.get_internal_dir() / "ffmpeg"

    @staticmethod
    def get_ffmpeg_exe() -> str:
        candidates = [
            RuntimePaths.get_ffmpeg_dir() / "ffmpeg.exe",
            RuntimePaths.get_ffmpeg_dir() / "bin" / "ffmpeg.exe",
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
        return RuntimePaths.get_internal_dir() / "resources"

    # --- DỮ LIỆU NGƯỜI DÙNG (READ/WRITE LOCALAPPDATA) ---
    @staticmethod
    def get_user_data_dir() -> Path:
        """Hàm Getter thuần túy, không chứa side-effect (không gọi mkdir)"""
        local_app_data = os.environ.get('LOCALAPPDATA')
        if not local_app_data:
            local_app_data = os.path.expanduser('~')
        return Path(local_app_data) / RuntimePaths.APP_NAME

    @staticmethod
    def get_models_dir() -> Path:
        return RuntimePaths.get_user_data_dir() / "models"

    @staticmethod
    def get_logs_dir() -> Path:
        return RuntimePaths.get_user_data_dir() / "logs"

    @staticmethod
    def get_media_imports_dir() -> Path:
        return RuntimePaths.get_user_data_dir() / "media_imports"

    @staticmethod
    def get_settings_file() -> Path:
        return RuntimePaths.get_user_data_dir() / "settings.json"

    @staticmethod
    def get_recovery_dir() -> Path:
        return RuntimePaths.get_user_data_dir() / "recovery"

    @staticmethod
    def get_recovery_sessions_dir() -> Path:
        return RuntimePaths.get_recovery_dir() / "sessions"

    @staticmethod
    def get_recovery_quarantine_dir() -> Path:
        return RuntimePaths.get_recovery_dir() / "quarantine"

    @classmethod
    def ensure_user_data_dirs(cls) -> None:
        """[S7.2-T18] Khởi tạo các thư mục dữ liệu cần thiết lúc khởi động ứng dụng"""
        cls.get_user_data_dir().mkdir(parents=True, exist_ok=True)
        cls.get_models_dir().mkdir(exist_ok=True)
        cls.get_logs_dir().mkdir(exist_ok=True)
        cls.get_media_imports_dir().mkdir(exist_ok=True)
        cls.get_recovery_dir().mkdir(parents=True, exist_ok=True)
        cls.get_recovery_sessions_dir().mkdir(parents=True, exist_ok=True)
        cls.get_recovery_quarantine_dir().mkdir(parents=True, exist_ok=True)
