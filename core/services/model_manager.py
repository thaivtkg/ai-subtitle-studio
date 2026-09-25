import errno
import shutil
import stat
from pathlib import Path
from core.runtime.runtime_paths import RuntimePaths


class ModelStorageError(RuntimeError):
    def __init__(self, operation: str, path: Path):
        self.operation = operation
        self.path = Path(path)
        super().__init__(f"Model storage unavailable during {operation}: {self.path}")


class ModelManager:
    SUPPORTED_MODELS = {
        "tiny": "150 MB", "base": "290 MB", "small": "960 MB",
        "medium": "3.0 GB", "large-v1": "5.8 GB", "large-v2": "5.8 GB",
        "large-v3": "5.8 GB", "large-v3-turbo": "1.6 GB"
    }

    @staticmethod
    def _storage_stat(path: Path, operation: str, models_dir: Path):
        try:
            return path.stat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ModelStorageError(operation, models_dir) from exc

    @staticmethod
    def _raise_invalid_storage(operation: str, models_dir: Path):
        cause = NotADirectoryError(
            errno.ENOTDIR, "Model storage path is not a directory", str(models_dir)
        )
        raise ModelStorageError(operation, models_dir) from cause

    @staticmethod
    def get_model_path_for_inference(model_size: str) -> str:
        models_dir = RuntimePaths.get_models_dir()
        offline_path = models_dir / model_size

        models_stat = ModelManager._storage_stat(
            models_dir, "resolve model", models_dir
        )
        if models_stat is None:
            return model_size
        if not stat.S_ISDIR(models_stat.st_mode):
            ModelManager._raise_invalid_storage("resolve model", models_dir)

        has_config = ModelManager._storage_stat(
            offline_path / "config.json", "resolve model", models_dir
        ) is not None
        has_bin = ModelManager._storage_stat(
            offline_path / "model.bin", "resolve model", models_dir
        ) is not None
        has_st = ModelManager._storage_stat(
            offline_path / "model.safetensors", "resolve model", models_dir
        ) is not None
        
        # [FIX WARNING 8] Sửa lỗi precedence logic and/or
        if has_config and (has_bin or has_st):
            return str(offline_path)

        return model_size

    @staticmethod
    def prepare_models_storage(operation: str) -> Path:
        models_dir = RuntimePaths.get_models_dir()
        existing_path_error = None
        try:
            try:
                models_dir.mkdir(parents=True, exist_ok=True)
            except FileExistsError as exc:
                # Probe separately: pathlib may report FileExistsError when
                # its exist_ok check cannot stat an inaccessible directory.
                existing_path_error = exc
            models_stat = models_dir.stat()
        except OSError as exc:
            raise ModelStorageError(operation, models_dir) from exc
        if not stat.S_ISDIR(models_stat.st_mode):
            cause = existing_path_error or NotADirectoryError(
                errno.ENOTDIR, "Model storage path is not a directory", str(models_dir)
            )
            raise ModelStorageError(operation, models_dir) from cause
        return models_dir

    @staticmethod
    def is_installed(model_size: str) -> bool:
        models_dir = RuntimePaths.get_models_dir()
        models_stat = ModelManager._storage_stat(
            models_dir, "discover models", models_dir
        )
        if models_stat is None:
            return False
        if not stat.S_ISDIR(models_stat.st_mode):
            ModelManager._raise_invalid_storage("discover models", models_dir)

        offline_path = models_dir / model_size

        has_config = ModelManager._storage_stat(
            offline_path / "config.json", "discover models", models_dir
        ) is not None
        has_bin = ModelManager._storage_stat(
            offline_path / "model.bin", "discover models", models_dir
        ) is not None
        has_st = ModelManager._storage_stat(
            offline_path / "model.safetensors", "discover models", models_dir
        ) is not None
        
        if has_config and (has_bin or has_st):
            return True
            
        # [FIX WARNING 9] Quét Cache nghiêm ngặt dựa vào manifest thực tế
        try:
            model_dirs = list(models_dir.iterdir())
        except OSError as exc:
            raise ModelStorageError("discover models", models_dir) from exc
        for model_dir in model_dirs:
            model_dir_stat = ModelManager._storage_stat(
                model_dir, "discover models", models_dir
            )
            if (
                model_dir_stat is not None
                and stat.S_ISDIR(model_dir_stat.st_mode)
                and f"faster-whisper-{model_size}" in model_dir.name
            ):
                snapshots_dir = model_dir / "snapshots"
                snapshots_stat = ModelManager._storage_stat(
                    snapshots_dir, "discover models", models_dir
                )
                if snapshots_stat is not None and stat.S_ISDIR(snapshots_stat.st_mode):
                    try:
                        snapshots = list(snapshots_dir.iterdir())
                    except OSError as exc:
                        raise ModelStorageError("discover models", models_dir) from exc
                    for snapshot in snapshots:
                        snapshot_stat = ModelManager._storage_stat(
                            snapshot, "discover models", models_dir
                        )
                        if (
                            snapshot_stat is not None
                            and stat.S_ISDIR(snapshot_stat.st_mode)
                            and ModelManager._storage_stat(
                                snapshot / "config.json", "discover models", models_dir
                            ) is not None
                        ):
                            return True
        return False

    @staticmethod
    def download_model_sync(model_size: str):
        """[BLOCKER 1 FIX] Download API - Tải model trực tiếp qua HuggingFace"""
        from faster_whisper import download_model
        # Tải và lưu vào đúng models_dir theo kiến trúc S7.2
        models_dir = ModelManager.prepare_models_storage("download model")
        download_model(model_size, cache_dir=str(models_dir))

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
        models_dir = ModelManager.prepare_models_storage("import model")
        target_dir = models_dir / model_size
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
