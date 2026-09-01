import json
import os
from pathlib import Path


class AtomicSnapshotStore:
    """Handle durable, atomic JSON snapshot persistence."""

    def read_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def write_json_atomic(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        try:
            if hasattr(os, "O_DIRECTORY"):
                directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except OSError:
            pass
