from typing import Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

from core.tutorial.models import SurfaceSpec


class AppRouter(QObject):
    """Business-layer router contract used by NavigationAdapter."""

    # ponytail: index correlation cannot distinguish repeated destinations or
    # late failures; add router operation IDs when overlapping jobs are supported.
    transition_finished = Signal(int)
    transition_failed = Signal(str)

    def current_index(self) -> int:
        raise NotImplementedError

    def current_subroute(self) -> Optional[str]:
        raise NotImplementedError

    def navigate_to_index(self, index: int, subroute: Optional[str]) -> None:
        raise NotImplementedError


class NavigationAdapter(QObject):
    # Physical stack indices, not MainWindow's sidebar navigation indices.
    ROUTE_MAP = {
        "dashboard": 0, "workspace": 1, "queue": 2,
        "draft_center": 3, "export_center": 4, "settings": 5,
    }
    INDEX_MAP = {index: route for route, index in ROUTE_MAP.items()}

    surface_ready = Signal(str, int, str)
    surface_failed = Signal(str, int, str, str)

    def __init__(self, router: AppRouter, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._router = router
        self._pending_request: Optional[Tuple[str, int, str, SurfaceSpec, Optional[int]]] = None
        self._queued_reason: Optional[str] = None
        self._queued = QTimer(self)
        self._queued.setSingleShot(True)
        self._queued.timeout.connect(self._on_queued_result)
        router.transition_finished.connect(self._on_transition_finished)
        router.transition_failed.connect(self._on_transition_failed)

    def navigate(
        self,
        surface: SurfaceSpec,
        *,
        session_id: str,
        generation: int,
        request_id: str,
    ) -> None:
        self.cancel_pending()
        target_index = self.ROUTE_MAP.get(surface.route)
        self._pending_request = (session_id, generation, request_id, surface, target_index)
        if target_index is None:
            self._queued_reason = "Unknown route"
            self._queued.start(0)
            return
        if self.current_surface() == surface:
            self._queued.start(0)
            return
        self._router.navigate_to_index(target_index, surface.subroute)

    def current_surface(self) -> SurfaceSpec:
        return SurfaceSpec(
            self.INDEX_MAP.get(self._router.current_index(), "unknown"),
            self._router.current_subroute(),
        )

    def cancel_pending(self) -> None:
        self._queued.stop()
        self._queued_reason = None
        self._pending_request = None

    def _on_queued_result(self) -> None:
        if self._pending_request is None:
            return
        session_id, generation, request_id, _, _ = self._pending_request
        reason = self._queued_reason
        self.cancel_pending()
        if reason is None:
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(session_id, generation, request_id, reason)

    def _on_transition_finished(self, destination_index: int) -> None:
        if self._pending_request is None or self._queued.isActive():
            return
        session_id, generation, request_id, target, target_index = self._pending_request
        if destination_index != target_index:
            return
        self._pending_request = None
        if self.current_surface() == target:
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(
                session_id, generation, request_id, "Route mismatch after transition"
            )

    def _on_transition_failed(self, reason: str) -> None:
        if self._pending_request is None or self._queued.isActive():
            return
        session_id, generation, request_id, _, _ = self._pending_request
        self._pending_request = None
        self.surface_failed.emit(session_id, generation, request_id, reason)
