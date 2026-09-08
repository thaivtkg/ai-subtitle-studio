import threading
from pathlib import Path
from typing import Sequence

from PIL import Image
from PIL import GifImagePlugin
from PySide6.QtGui import QImage

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError


_GIF_WRITE_LOCK = threading.Lock()


class PillowAssetEncoder:
    @staticmethod
    def _pil_image(frame: QImage) -> Image.Image:
        if frame.isNull():
            raise ValueError("cannot encode a null QImage")
        rgba = frame.convertToFormat(QImage.Format.Format_RGBA8888)
        size = rgba.sizeInBytes()
        data = bytes(rgba.bits()[:size])
        return Image.frombytes("RGBA", (rgba.width(), rgba.height()), data)

    def encode_png(self, frame: QImage, path: Path) -> None:
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._pil_image(frame).save(path, format="PNG")
        except Exception as error:
            raise CaptureRunError(
                CaptureErrorCode.ENCODE_FAILED,
                f"PNG encoding failed: {error}",
            ) from error

    def encode_gif(self, frames: Sequence[QImage], path: Path, fps: int) -> None:
        if len(frames) < 2:
            raise CaptureRunError(
                CaptureErrorCode.ENCODE_FAILED,
                "GIF encoding requires at least two frames",
            )
        if fps <= 0:
            raise CaptureRunError(CaptureErrorCode.ENCODE_FAILED, "fps must be > 0")
        try:
            images = [self._pil_image(frame) for frame in frames]
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Pillow coalesces identical adjacent frames even with optimize=False.
            # Keep its writer serialized and force a full-canvas descriptor for those slots.
            original_getbbox = GifImagePlugin._getbbox

            def preserve_identical_slots(previous, current):
                delta, bbox = original_getbbox(previous, current)
                if bbox is None:
                    return delta, (0, 0, current.width, current.height)
                return delta, bbox

            with _GIF_WRITE_LOCK:
                GifImagePlugin._getbbox = preserve_identical_slots
                try:
                    images[0].save(
                        path,
                        format="GIF",
                        save_all=True,
                        append_images=images[1:],
                        duration=round(1000 / fps),
                        loop=0,
                        disposal=2,
                        optimize=False,
                    )
                finally:
                    GifImagePlugin._getbbox = original_getbbox
        except CaptureRunError:
            raise
        except Exception as error:
            raise CaptureRunError(
                CaptureErrorCode.ENCODE_FAILED,
                f"GIF encoding failed: {error}",
            ) from error
