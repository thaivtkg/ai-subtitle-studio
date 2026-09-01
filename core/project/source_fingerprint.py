import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceInfo:
    path: str
    filename: str
    size_bytes: int
    modified_at: float
    fingerprint: str


def generate_source_info(video_path: str) -> SourceInfo:
    """Return canonical SourceInfo using fast SHA-256 fingerprint."""
    stat = os.stat(video_path)
    size_bytes = stat.st_size
    modified_at = stat.st_mtime

    hasher = hashlib.sha256()
    hasher.update(str(size_bytes).encode("utf-8"))
    sample_size = 1024 * 1024
    with open(video_path, "rb") as handle:
        if size_bytes <= sample_size * 2:
            hasher.update(handle.read())
        else:
            hasher.update(handle.read(sample_size))
            handle.seek(-sample_size, os.SEEK_END)
            hasher.update(handle.read(sample_size))

    return SourceInfo(
        path=video_path,
        filename=os.path.basename(video_path),
        size_bytes=size_bytes,
        modified_at=modified_at,
        fingerprint=hasher.hexdigest(),
    )
