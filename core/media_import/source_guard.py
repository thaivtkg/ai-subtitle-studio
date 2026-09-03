from pathlib import Path


class SourceGuard:
    @staticmethod
    def is_confined(file_path: str | Path, allowed_root: str | Path) -> bool:
        try:
            target = Path(file_path).resolve()
            root = Path(allowed_root).resolve()
            return target == root or root in target.parents
        except (OSError, ValueError):
            return False

    @staticmethod
    def verify_integrity(file_path: str | Path, min_size: int = 1) -> bool:
        path = Path(file_path)
        try:
            return path.is_file() and path.stat().st_size >= min_size
        except OSError:
            return False
