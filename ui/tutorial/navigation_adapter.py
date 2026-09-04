from typing import Optional, Tuple
from itertools import count

from PySide6.QtCore import QObject, QTimer, Signal

from core.tutorial.models import SurfaceSpec


class AppRouter(QObject):
    """Router contract exposing an operation identity for every transition."""

    transition_finished = Signal(str, int)
    transition_failed = Signal(str, str)

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
        self._pending_request: Optional[Tuple[str, int, str, SurfaceSpec, int, str]] = None
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
        if target_index is None:
            self._pending_request = (session_id, generation, request_id, surface, -1, "")
            self._queued_reason = "Unknown route"
            self._queued.start(0)
            return
        if self.current_surface() == surface:
            self._pending_request = (session_id, generation, request_id, surface, target_index, "")
            self._queued.start(0)
            return
        operation_id = self._router.navigate_to_index(target_index, surface.subroute)
        self._pending_request = (
            session_id, generation, request_id, surface, target_index, operation_id
        )

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
        session_id, generation, request_id, _, _, _ = self._pending_request
        reason = self._queued_reason
        self.cancel_pending()
        if reason is None:
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(session_id, generation, request_id, reason)

    def _on_transition_finished(self, operation_id: str, destination_index: int) -> None:
        if self._pending_request is None or self._queued.isActive():
            return
        session_id, generation, request_id, target, target_index, pending_operation_id = self._pending_request
        if operation_id != pending_operation_id or destination_index != target_index:
            return
        self._pending_request = None
        if self.current_surface() == target:
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(
                session_id, generation, request_id, "Route mismatch after transition"
            )

    def _on_transition_failed(self, operation_id: str, reason: str) -> None:
        if self._pending_request is None or self._queued.isActive():
            return
        session_id, generation, request_id, _, _, pending_operation_id = self._pending_request
        if operation_id != pending_operation_id:
            return
        self._pending_request = None
        self.surface_failed.emit(session_id, generation, request_id, reason)


class MainWindowRouter(AppRouter):
    """Concrete adapter for MainWindow, AnimatedStack, and workspace dock tabs."""

    INDEX_TO_NAV_INDEX = {0: 0, 1: 1, 2: 3, 3: 4, 4: 5, 5: 6}
    SUBROUTE_TO_TAB = {"generate": 0, "context": 1, "style": 2, "log": 3}
    TAB_TO_SUBROUTE = {index: name for name, index in SUBROUTE_TO_TAB.items()}

    def __init__(self, window: QObject, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._window = window
        self._ids = count(1)
        self._active_operation_id: Optional[str] = None
        self._stack = window.stack
        self._stack.anim_group.finished.connect(self._on_transition_finished)

    def current_index(self) -> int:
        return self._stack.current_index

    def current_subroute(self) -> Optional[str]:
        if self.current_index() != NavigationAdapter.ROUTE_MAP["workspace"]:
            return None
        return self.TAB_TO_SUBROUTE.get(self._window.dock_tabs.currentIndex())

    def navigate_to_index(self, index: int, subroute: Optional[str]) -> str:
        operation_id = f"op-{next(self._ids)}"
        self._active_operation_id = operation_id
        if index == NavigationAdapter.ROUTE_MAP["workspace"] and subroute in self.SUBROUTE_TO_TAB:
            self._window.dock_tabs.setCurrentIndex(self.SUBROUTE_TO_TAB[subroute])
        nav_index = self.INDEX_TO_NAV_INDEX.get(index)
        if nav_index is None:
            QTimer.singleShot(0, lambda: self.transition_failed.emit(operation_id, "Unknown index"))
        else:
            self._window.switch_page(nav_index)
            if index == self.current_index():
                QTimer.singleShot(0, lambda: self._finish_operation(operation_id, index))
        return operation_id

    def _on_transition_finished(self) -> None:
        if self._active_operation_id is None:
            return
        operation_id = self._active_operation_id
        self._active_operation_id = None
        self.transition_finished.emit(operation_id, self.current_index())

    def _finish_operation(self, operation_id: str, index: int) -> None:
        if operation_id != self._active_operation_id:
            return
        self._active_operation_id = None
        self.transition_finished.emit(operation_id, index)
