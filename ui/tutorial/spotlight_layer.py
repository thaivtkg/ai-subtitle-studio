import weakref
from typing import Any, List, Optional

import shiboken6
from PySide6.QtCore import QObject, QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget

from core.tutorial.models import AnchorHandle, CalloutSpec, CalloutPlacement, DemoSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.callout_widget import TourCalloutWidget


class DimWidget(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.hide()

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()


class BorderWidget(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("border: 2px solid #007bff; border-radius: 4px; background: transparent;")
        self.hide()


class SpotlightLayerAdapter(QObject):
    """Render a physical four-sided mask around one real target widget."""

    def __init__(self, registry: AnchorRegistry, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._registry = registry
        self._host_window_ref: Optional[weakref.ReferenceType[QWidget]] = None
        self._target_widget_ref: Optional[weakref.ReferenceType[QWidget]] = None
        self._ancestor_refs: List[weakref.ReferenceType[QWidget]] = []
        self._top_dim: Optional[DimWidget] = None
        self._bottom_dim: Optional[DimWidget] = None
        self._left_dim: Optional[DimWidget] = None
        self._right_dim: Optional[DimWidget] = None
        self._border_widget: Optional[BorderWidget] = None
        self._callout_widget: Optional[TourCalloutWidget] = None
        self._current_callout: Optional[CalloutSpec] = None

    def attach_host(self, host: Any) -> bool:
        if not isinstance(host, QWidget) or not shiboken6.isValid(host):
            return False
        self._ensure_ui_initialized(host)
        self._host_window_ref = weakref.ref(host)
        return True

    def _ensure_ui_initialized(self, host: QWidget) -> None:
        if self._top_dim and shiboken6.isValid(self._top_dim) and self._top_dim.parent() is host:
            return
        self._cleanup_ui()
        self._top_dim = DimWidget(host)
        self._bottom_dim = DimWidget(host)
        self._left_dim = DimWidget(host)
        self._right_dim = DimWidget(host)
        self._border_widget = BorderWidget(host)
        self._callout_widget = TourCalloutWidget(host)
        self._callout_widget.hide()

    def _cleanup_ui(self) -> None:
        for widget in (self._top_dim, self._bottom_dim, self._left_dim, self._right_dim, self._border_widget, self._callout_widget):
            if widget is not None and shiboken6.isValid(widget):
                widget.hide()
                widget.deleteLater()
        self._top_dim = self._bottom_dim = self._left_dim = self._right_dim = self._border_widget = None
        self._callout_widget = None

    def _update_geometry(self) -> None:
        host = self._host_window_ref() if self._host_window_ref else None
        if host is None or not shiboken6.isValid(host) or self._callout_widget is None:
            return
        dims = (self._top_dim, self._bottom_dim, self._left_dim, self._right_dim)
        if any(dim is None for dim in dims) or self._border_widget is None:
            return
        target = self._target_widget_ref() if self._target_widget_ref else None
        if target is not None and shiboken6.isValid(target) and target.isVisible():
            pos = target.mapTo(host, QPoint(0, 0))
            tx, ty, tw, th = pos.x(), pos.y(), target.width(), target.height()
            hw, hh = host.width(), host.height()
            self._top_dim.setGeometry(0, 0, hw, ty)
            self._bottom_dim.setGeometry(0, ty + th, hw, hh - ty - th)
            self._left_dim.setGeometry(0, ty, tx, th)
            self._right_dim.setGeometry(tx + tw, ty, hw - tx - tw, th)
            self._border_widget.setGeometry(tx - 2, ty - 2, tw + 4, th + 4)
            for dim in dims:
                dim.raise_()
                dim.show()
            self._border_widget.raise_()
            self._border_widget.show()
            self._callout_widget.adjustSize()
            cw, ch = self._callout_widget.width(), self._callout_widget.height()
            placement = self._current_callout.placement if self._current_callout else CalloutPlacement.AUTO
            if placement is CalloutPlacement.CENTER:
                placement = CalloutPlacement.AUTO
            cx, cy = tx, ty + th + 10
            if placement is CalloutPlacement.TOP:
                cy = ty - ch - 10
            elif placement is CalloutPlacement.BOTTOM:
                cy = ty + th + 10
            elif placement is CalloutPlacement.LEFT:
                cx, cy = tx - cw - 10, ty
            elif placement is CalloutPlacement.RIGHT:
                cx, cy = tx + tw + 10, ty
            elif placement is CalloutPlacement.AUTO:
                if cy + ch > hh:
                    cy = ty - ch - 10
                if cy < 0 and tx + tw + cw + 10 <= hw:
                    cx, cy = tx + tw + 10, ty
            cx = max(0, min(cx, max(0, hw - cw)))
            cy = max(0, min(cy, max(0, hh - ch)))
            self._callout_widget.move(cx, cy)
        else:
            self._top_dim.setGeometry(host.rect())
            self._top_dim.raise_()
            self._top_dim.show()
            for dim in dims[1:]:
                dim.hide()
            self._border_widget.hide()
            self._callout_widget.adjustSize()
            self._callout_widget.move(
                (host.width() - self._callout_widget.width()) // 2,
                (host.height() - self._callout_widget.height()) // 2,
            )
        self._callout_widget.raise_()
        self._callout_widget.show()

    def _bind_events(self, host: QWidget, target: Optional[QWidget]) -> None:
        self._unbind_events()
        self._host_window_ref = weakref.ref(host)
        host.installEventFilter(self)
        if target is not None:
            self._target_widget_ref = weakref.ref(target)
            w = target
            while w is not None and w is not host:
                w.installEventFilter(self)
                self._ancestor_refs.append(weakref.ref(w))
                w = w.parentWidget()

    def _unbind_events(self) -> None:
        host = self._host_window_ref() if self._host_window_ref else None
        if host is not None and shiboken6.isValid(host):
            host.removeEventFilter(self)
        target = self._target_widget_ref() if self._target_widget_ref else None
        if target is not None and shiboken6.isValid(target):
            target.removeEventFilter(self)
        for ref in self._ancestor_refs:
            widget = ref()
            if widget is not None and shiboken6.isValid(widget):
                widget.removeEventFilter(self)
        self._ancestor_refs.clear()
        self._host_window_ref = None
        self._target_widget_ref = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide):
            self._update_geometry()
        return False

    def show_target(self, handle: AnchorHandle, callout: CalloutSpec, controls: Any) -> bool:
        self._current_callout = callout
        target = self._registry.get_widget(handle)
        if target is None or not shiboken6.isValid(target):
            self.show_info_without_target(callout, controls)
            return False
        host = target.window()
        if host is None or not shiboken6.isValid(host):
            return False
        self._ensure_ui_initialized(host)
        self._bind_events(host, target)
        self._callout_widget.setup(callout, controls)
        self._update_geometry()
        return True

    def show_info_without_target(self, callout: CalloutSpec, controls: Any) -> None:
        self._current_callout = None
        app = QApplication.instance()
        host = app.activeWindow() if app else None
        if host is None:
            return
        self._ensure_ui_initialized(host)
        self._bind_events(host, None)
        self._callout_widget.setup(callout, controls)
        self._update_geometry()

    def show_demo(self, demo: DemoSpec, callout: CalloutSpec, controls: Any) -> bool:
        self._current_callout = None
        self.show_info_without_target(callout, controls)
        return True

    def show_recovery(
        self, message: str, retry_enabled: bool, skip_enabled: bool, controls: Any = None
    ) -> None:
        self._current_callout = None
        app = QApplication.instance()
        host = app.activeWindow() if app else None
        if host is None:
            return
        self._ensure_ui_initialized(host)
        self._bind_events(host, None)
        self._callout_widget.set_recovery_message(message, controls, retry_enabled, skip_enabled)
        self._update_geometry()

    def hide_step(self) -> None:
        self._unbind_events()
        for dim in (self._top_dim, self._bottom_dim, self._left_dim, self._right_dim):
            if dim is not None:
                dim.hide()
        if self._border_widget is not None:
            self._border_widget.hide()
        if self._callout_widget is not None:
            self._callout_widget.hide()
        self._current_callout = None

    def detach_host(self) -> None:
        self._unbind_events()
        self._cleanup_ui()
