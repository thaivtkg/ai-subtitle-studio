import weakref
from typing import Callable, Dict, Optional

try:
    import shiboken6
except ImportError:
    from PySide6 import shiboken6
from PySide6.QtWidgets import QWidget

from core.tutorial.models import AnchorHandle, AnchorResolution, AnchorStatus


class AnchorRegistry:
    """Resolve semantic anchor IDs without owning the underlying QWidget."""

    def __init__(self) -> None:
        self._resolvers: Dict[str, Callable[[], Optional[QWidget]]] = {}
        self._handle_map: Dict[AnchorHandle, weakref.ReferenceType[QWidget]] = {}
        self._generation = 0

    def register(self, anchor_id: str, widget: QWidget) -> None:
        """Register a static widget without retaining its Python wrapper."""
        self.register_resolver(anchor_id, weakref.ref(widget))

    def register_resolver(
        self, anchor_id: str, resolver: Callable[[], Optional[QWidget]]
    ) -> None:
        """Dynamic resolvers must use weak captures for widgets and UI owners."""
        self.unregister(anchor_id)
        self._resolvers[anchor_id] = resolver

    def unregister(self, anchor_id: str) -> None:
        self._resolvers.pop(anchor_id, None)
        for handle in list(self._handle_map):
            if handle.anchor_id == anchor_id:
                del self._handle_map[handle]

    def clear(self) -> None:
        self._resolvers.clear()
        self._handle_map.clear()

    def resolve(self, anchor_id: str) -> AnchorResolution:
        resolver = self._resolvers.get(anchor_id)
        if resolver is None:
            return AnchorResolution(status=AnchorStatus.NOT_FOUND)

        try:
            widget = resolver()
        except Exception as error:
            return AnchorResolution(status=AnchorStatus.NOT_FOUND, reason=str(error))

        if widget is None:
            return AnchorResolution(status=AnchorStatus.NOT_FOUND)
        if not isinstance(widget, QWidget) or not shiboken6.isValid(widget):
            return AnchorResolution(status=AnchorStatus.INVALID)
        if not widget.isVisible() or widget.size().isEmpty():
            return AnchorResolution(status=AnchorStatus.NOT_VISIBLE)

        host = widget.window()
        host_id = host.objectName() if host and host.objectName() else "main"
        self._generation += 1
        handle = AnchorHandle(anchor_id, host_id, self._generation)
        self._handle_map[handle] = weakref.ref(widget)
        return AnchorResolution(status=AnchorStatus.RESOLVED, handle=handle)

    def get_widget(self, handle: AnchorHandle) -> Optional[QWidget]:
        widget_ref = self._handle_map.get(handle)
        if widget_ref is None:
            return None
        widget = widget_ref()
        return widget if widget is not None and shiboken6.isValid(widget) else None
