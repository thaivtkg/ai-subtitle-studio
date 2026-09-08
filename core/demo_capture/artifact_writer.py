import os
from pathlib import Path
from typing import Union

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import OutputSpec


class ArtifactWriter:
    def __init__(self, asset_root: Union[str, Path]) -> None:
        self._root = Path(asset_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _confined(self, path: Union[str, Path]) -> Path:
        resolved = Path(path).resolve()
        if resolved != self._root and self._root not in resolved.parents:
            raise CaptureRunError(
                CaptureErrorCode.ARTIFACT_COMMIT_FAILED,
                f"Path escapes asset root: {path}",
            )
        return resolved

    def commit(self, staged_path: Union[str, Path], output_spec: OutputSpec) -> None:
        try:
            staged = self._confined(staged_path)
            final = self._confined(self._root / output_spec.filename)
            if not staged.is_file():
                raise FileNotFoundError(staged)
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
            return final
        except CaptureRunError:
            raise
        except Exception as error:
            raise CaptureRunError(
                CaptureErrorCode.ARTIFACT_COMMIT_FAILED,
                f"Artifact commit failed: {error}",
            ) from error

    def cleanup(self, staged_path: Union[str, Path]) -> None:
        staged = self._confined(staged_path)
        if staged.is_file():
            staged.unlink()
