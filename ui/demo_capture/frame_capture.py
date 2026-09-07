from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from core.demo_capture.models import CaptureScope, CaptureTarget
from core.demo_capture.ports import TargetResolverPort


class FrameCaptureService:
    def __init__(self, resolver: TargetResolverPort):
        self._resolver = resolver

    def capture(self, target: CaptureTarget, main_window: QWidget) -> QImage:
        if target.scope == CaptureScope.FULL_WINDOW:
            return main_window.grab().toImage()

        widget = self._resolver.resolve_widget(target.semantic_id)
        root = widget.window() if widget.window() else main_window
        origin = widget.mapTo(root, QPoint(0, 0))
        padding = target.padding
        rect = QRect(origin, widget.size()).adjusted(-padding, -padding, padding, padding)
        rect = rect.intersected(root.rect())
        return root.grab().copy(rect).toImage()
