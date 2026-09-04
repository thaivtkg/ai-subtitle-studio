from typing import Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

from core.tutorial.models import SurfaceSpec


class AppRouter(QObject):
    """Business-layer router contract used by NavigationAdapter."""

    transition_finished = Signal()
    transition_failed = Signal(str)

    def current_route(self) -> str:
        raise NotImplementedError

    def current_subroute(self) -> Optional[str]:
        raise NotImplementedError

    def navigate_to(self, route: str, subroute: Optional[str]) -> None:
        raise NotImplementedError


class NavigationAdapter(QObject):
    surface_ready = Signal(str, int, str)
    surface_failed = Signal(str, int, str, str)

    def __init__(self, router: AppRouter, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._router = router
        self._pending_request: Optional[Tuple[str, int, str, SurfaceSpec]] = None
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
        if self.current_surface() == surface:
            QTimer.singleShot(
                0,
                lambda: self.surface_ready.emit(session_id, generation, request_id),
            )
            return

        self._pending_request = (session_id, generation, request_id, surface)
        self._router.navigate_to(surface.route, surface.subroute)

    def current_surface(self) -> SurfaceSpec:
        return SurfaceSpec(self._router.current_route(), self._router.current_subroute())

    def cancel_pending(self) -> None:
        self._pending_request = None

    def _on_transition_finished(self) -> None:
        if self._pending_request is None:
            return
        session_id, generation, request_id, target = self._pending_request
        self._pending_request = None
        if self.current_surface() == target:
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(
                session_id, generation, request_id, "Route mismatch after transition"
            )

    def _on_transition_failed(self, reason: str) -> None:
        if self._pending_request is None:
            return
        session_id, generation, request_id, _ = self._pending_request
        self._pending_request = None
        self.surface_failed.emit(session_id, generation, request_id, reason)
