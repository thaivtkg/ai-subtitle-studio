import os
import shutil
from pathlib import Path
from core.runtime.runtime_paths import RuntimePaths

class ModelManager:
    """
    [S7.2-T13 -> T16] Model Manager: Quản lý vòng đời Model AI
    Hỗ trợ phát hiện, xóa và nạp Model Offline cho môi trường đóng gói (Clean Machine).
    """
    
    SUPPORTED_MODELS = {
        "tiny": "150 MB",
        "base": "290 MB",
        "small": "960 MB",
        "medium": "3.0 GB",
        "large-v1": "5.8 GB",
        "large-v2": "5.8 GB",
        "large-v3": "5.8 GB",
        "large-v3-turbo": "1.6 GB"
    }

    @staticmethod
    def get_model_path_for_inference(model_size: str) -> str:
        """
        Trích xuất đường dẫn an toàn để nạp vào WhisperModel.
        Ưu tiên đường dẫn Offline tuyệt đối nếu có, ngược lại trả về tên model để AI tự tải.
        """
        models_dir = RuntimePaths.get_models_dir()
        
        # 1. Ưu tiên kiểm tra định dạng Offline chuẩn (models/large-v3-turbo)
        offline_path = models_dir / model_size
        if (offline_path / "config.json").exists() and (offline_path / "model.bin").exists() or (offline_path / "model.safetensors").exists():
            return str(offline_path)

        # 2. Fallback: Trả về tên mặc định để faster_whisper tải qua Hugging Face (sẽ lưu vào download_root)
        return model_size

    @staticmethod
    def is_installed(model_size: str) -> bool:
        """Kiểm tra model đã có sẵn trên máy chưa"""
        models_dir = RuntimePaths.get_models_dir()
        
        # 1. Kiểm tra định dạng Offline
        offline_path = models_dir / model_size
        if (offline_path / "config.json").exists():
            return True
            
        # 2. Kiểm tra định dạng Hugging Face Cache
        # faster-whisper tải model dưới dạng thư mục "models--[org]--faster-whisper-[size]"
        for d in models_dir.iterdir():
            if d.is_dir() and model_size in d.name and "faster-whisper" in d.name:
                snapshots_dir = d / "snapshots"
                if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
                    return True
                    
        return False

    @staticmethod
    def delete_model(model_size: str) -> bool:
        """Xóa tận gốc model để giải phóng ổ cứng (S7.2-T15)"""
        models_dir = RuntimePaths.get_models_dir()
        deleted = False
        
        # Xóa dạng Offline
        offline_path = models_dir / model_size
        if offline_path.exists():
            shutil.rmtree(offline_path, ignore_errors=True)
            deleted = True
            
        # Xóa dạng Cache HF
        for d in models_dir.iterdir():
            if d.is_dir() and model_size in d.name and "faster-whisper" in d.name:
                shutil.rmtree(d, ignore_errors=True)
                deleted = True
                
        return deleted

    @staticmethod
    def import_offline_model(model_size: str, source_folder: str) -> bool:
        """[S7.2-T16] Import Model từ USB/Thư mục có sẵn vào %LOCALAPPDATA%"""
        source_path = Path(source_folder)
        if not source_path.exists() or not (source_path / "config.json").exists():
            raise ValueError("Thư mục không hợp lệ! Cần chứa file config.json của CTranslate2.")
            
        target_dir = RuntimePaths.get_models_dir() / model_size
        shutil.copytree(source_path, target_dir, dirs_exist_ok=True)
        return True

    @classmethod
    def get_discovery_list(cls) -> list:
        """[S7.2-T14] Lấy danh sách thống kê toàn bộ model phục vụ UI"""
        results = []
        for size, weight in cls.SUPPORTED_MODELS.items():
            results.append({
                "size": size,
                "weight": weight,
                "installed": cls.is_installed(size)
            })
        return results