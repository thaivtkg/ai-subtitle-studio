from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QColor

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError


class FrameNormalizer:
    def normalize(self, frames: Sequence[QImage], output_scale: float) -> tuple[QImage, ...]:
        if not frames:
            raise CaptureRunError(CaptureErrorCode.CAPTURE_FAILED, "Empty frame sequence")

        max_width = max(frame.width() for frame in frames)
        max_height = max(frame.height() for frame in frames)
        result = []
        for frame in frames:
            canvas = QImage(max_width, max_height, QImage.Format.Format_ARGB32)
            canvas.fill(QColor(0, 0, 0, 0))
            dx = (max_width - frame.width()) // 2
            dy = (max_height - frame.height()) // 2
            painter = QPainter(canvas)
            painter.drawImage(dx, dy, frame)
            painter.end()

            if output_scale != 1.0:
                canvas = canvas.scaled(
                    int(max_width * output_scale),
                    int(max_height * output_scale),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            result.append(canvas)
        return tuple(result)
