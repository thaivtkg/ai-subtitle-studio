from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import OutputFormat, OutputSpec


@dataclass(frozen=True)
class AssetValidationPolicy:
    max_width: int = 1600
    max_height: int = 1200
    max_pixels: int = 1_920_000
    max_png_bytes: int = 2 * 1024 * 1024
    max_gif_bytes: int = 8 * 1024 * 1024
    min_gif_frames: int = 2
    max_gif_frames: int = 200
    max_gif_duration_ms: int = 20_000


class TutorialAssetValidator:
    def __init__(self, policy: AssetValidationPolicy = AssetValidationPolicy()) -> None:
        self._policy = policy

    def _fail(self, message: str, code: CaptureErrorCode = CaptureErrorCode.ASSET_INVALID) -> None:
        raise CaptureRunError(code, message)

    def validate_file(self, path: Path, output_spec: OutputSpec) -> None:
        path = Path(path)
        if not path.is_file():
            self._fail(f"Asset does not exist: {path}", CaptureErrorCode.ASSET_NOT_FOUND)
        size = path.stat().st_size
        max_bytes = (
            self._policy.max_png_bytes
            if output_spec.format == OutputFormat.PNG
            else self._policy.max_gif_bytes
        )
        if size > max_bytes:
            self._fail(f"Asset exceeds size limit: {path}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                actual_format = image.format
                expected_format = output_spec.format.value
                if actual_format != expected_format:
                    self._fail(f"Expected {expected_format}, got {actual_format}")
                if image.width > self._policy.max_width or image.height > self._policy.max_height:
                    self._fail("Asset dimensions exceed limits")
                if image.width * image.height > self._policy.max_pixels:
                    self._fail("Asset pixel count exceeds limit")
                if output_spec.format == OutputFormat.PNG:
                    if getattr(image, "n_frames", 1) != 1:
                        self._fail("PNG must contain exactly one frame")
                    return
                self._validate_gif(image)
        except (CaptureRunError, UnidentifiedImageError, OSError, ValueError) as error:
            if isinstance(error, CaptureRunError):
                raise
            self._fail(f"Asset decode failed: {error}")

    def _validate_gif(self, image: Any) -> None:
        frame_count = getattr(image, "n_frames", 1)
        if not self._policy.min_gif_frames <= frame_count <= self._policy.max_gif_frames:
            self._fail("GIF frame count is outside limits")
        canonical_size = image.size
        duration = 0
        for index in range(frame_count):
            image.seek(index)
            if image.size != canonical_size:
                self._fail("GIF frames must have identical dimensions")
            tile = getattr(image, "tile", ())
            if tile:
                left, top, right, bottom = tile[0][1]
                if (right - left, bottom - top) != canonical_size:
                    self._fail("GIF frames must have identical dimensions")
            duration += int(image.info.get("duration", 0) or 0)
        if duration > self._policy.max_gif_duration_ms:
            self._fail("GIF duration exceeds limit")

    def validate_registry_assets(self, registry: Any, asset_root: Path) -> None:
        root = Path(asset_root).resolve()
        for scenario in registry.all():
            path = (root / scenario.output.filename).resolve()
            if path.parent != root:
                self._fail("Asset path escapes asset root")
            self.validate_file(path, scenario.output)
