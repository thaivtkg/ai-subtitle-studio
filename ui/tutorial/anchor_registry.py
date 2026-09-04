import weakref
from typing import Callable, Dict, Optional

import shiboken6
from PySide6.QtWidgets import QWidget

from core.tutorial.models import AnchorHandle, AnchorResolution, AnchorStatus


class AnchorRegistry:
    """Resolve semantic anchor IDs without owning the underlying QWidget."""

    def __init__(self) -> None:
        self._resolvers: Dict[str, Callable[[], Optional[QWidget]]] = {}
        self._handle_map: Dict[AnchorHandle, weakref.ReferenceType[QWidget]] = {}
        self._generation = 0

    def register_resolver(
        self, anchor_id: str, resolver: Callable[[], Optional[QWidget]]
    ) -> None:
        self._resolvers[anchor_id] = resolver

    def resolve(self, anchor_id: str) -> AnchorResolution:
        resolver = self._resolvers.get(anchor_id)
        if resolver is None:
            return AnchorResolution(status=AnchorStatus.NOT_FOUND)

        try:
            widget = resolver()
        except Exception:
            return AnchorResolution(status=AnchorStatus.NOT_FOUND)

        if widget is None or not shiboken6.isValid(widget):
            return AnchorResolution(status=AnchorStatus.NOT_FOUND)
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
