import os
import shutil
from pathlib import Path
from core.runtime.runtime_paths import RuntimePaths

class ModelManager:
    SUPPORTED_MODELS = {
        "tiny": "150 MB", "base": "290 MB", "small": "960 MB",
        "medium": "3.0 GB", "large-v1": "5.8 GB", "large-v2": "5.8 GB",
        "large-v3": "5.8 GB", "large-v3-turbo": "1.6 GB"
    }

    @staticmethod
    def get_model_path_for_inference(model_size: str) -> str:
        models_dir = RuntimePaths.get_models_dir()
        offline_path = models_dir / model_size
        
        has_config = (offline_path / "config.json").exists()
        has_bin = (offline_path / "model.bin").exists()
        has_st = (offline_path / "model.safetensors").exists()
        
        # [FIX WARNING 8] Sửa lỗi precedence logic and/or
        if has_config and (has_bin or has_st):
            return str(offline_path)

        return model_size

    @staticmethod
    def is_installed(model_size: str) -> bool:
        models_dir = RuntimePaths.get_models_dir()
        offline_path = models_dir / model_size
        
        has_config = (offline_path / "config.json").exists()
        has_bin = (offline_path / "model.bin").exists()
        has_st = (offline_path / "model.safetensors").exists()
        
        if has_config and (has_bin or has_st):
            return True
            
        # [FIX WARNING 9] Quét Cache nghiêm ngặt dựa vào manifest thực tế
        for d in models_dir.iterdir():
            if d.is_dir() and f"faster-whisper-{model_size}" in d.name:
                snapshots_dir = d / "snapshots"
                if snapshots_dir.exists():
                    for snap in snapshots_dir.iterdir():
                        if snap.is_dir() and (snap / "config.json").exists():
                            return True
        return False

    @staticmethod
    def download_model_sync(model_size: str):
        """[BLOCKER 1 FIX] Download API - Tải model trực tiếp qua HuggingFace"""
        from faster_whisper import download_model
        # Tải và lưu vào đúng models_dir theo kiến trúc S7.2
        download_model(model_size, cache_dir=str(RuntimePaths.get_models_dir()))

    @staticmethod
    def delete_model(model_size: str) -> bool:
        models_dir = RuntimePaths.get_models_dir()
        deleted = False
        offline_path = models_dir / model_size
        if offline_path.exists():
            shutil.rmtree(offline_path, ignore_errors=True)
            deleted = True
            
        for d in models_dir.iterdir():
            if d.is_dir() and f"faster-whisper-{model_size}" in d.name:
                shutil.rmtree(d, ignore_errors=True)
                deleted = True
        return deleted

    @staticmethod
    def import_offline_model(model_size: str, source_folder: str) -> bool:
        source_path = Path(source_folder)
        if not source_path.exists() or not (source_path / "config.json").exists():
            raise ValueError("Thư mục không hợp lệ! Cần chứa file config.json của CTranslate2.")
        target_dir = RuntimePaths.get_models_dir() / model_size
        shutil.copytree(source_path, target_dir, dirs_exist_ok=True)
        return True

    @classmethod
    def get_discovery_list(cls) -> list:
        results = []
        for size, weight in cls.SUPPORTED_MODELS.items():
            results.append({
                "size": size,
                "weight": weight,
                "installed": cls.is_installed(size)
            })
        return results