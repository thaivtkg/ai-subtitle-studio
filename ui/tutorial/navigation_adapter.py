from typing import Optional, Tuple
from itertools import count

from PySide6.QtCore import QAbstractAnimation, QObject, QTimer, Signal

from core.tutorial.models import SurfaceSpec


class AppRouter(QObject):
    """Router contract exposing an operation identity for every transition."""

    transition_finished = Signal(str, int)
    transition_failed = Signal(str, str)

    def current_index(self) -> int:
        raise NotImplementedError

    def current_subroute(self) -> Optional[str]:
        raise NotImplementedError

    def navigate_to_index(self, index: int, subroute: Optional[str]) -> str:
        raise NotImplementedError

    def cancel_operation(self) -> None:
        """Cancel router-owned settling work, if any."""


class NavigationAdapter(QObject):
    # Physical stack indices, not MainWindow's sidebar navigation indices.
    ROUTE_MAP = {
        "dashboard": 0, "workspace": 1, "queue": 2,
        "draft_center": 3, "export_center": 4, "settings": 5,
        "help": 6,
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
        if self._surface_matches(self.current_surface(), surface):
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
        self._router.cancel_operation()
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
        if self._surface_matches(self.current_surface(), target):
            self.surface_ready.emit(session_id, generation, request_id)
        else:
            self.surface_failed.emit(
                session_id, generation, request_id, "Route mismatch after transition"
            )

    @staticmethod
    def _surface_matches(current: SurfaceSpec, target: SurfaceSpec) -> bool:
        return current.route == target.route and (
            target.subroute is None or current.subroute == target.subroute
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

    INDEX_TO_NAV_INDEX = {0: 0, 1: 1, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}
    SUBROUTE_TO_TAB = {"generate": 0, "context": 1, "style": 2, "log": 3}
    TAB_TO_SUBROUTE = {index: name for name, index in SUBROUTE_TO_TAB.items()}

    def __init__(self, window: QObject, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._window = window
        self._ids = count(1)
        self._active_operation_id: Optional[str] = None
        self._stack = window.stack
        self._stack.anim_group.finished.connect(self._on_transition_finished)
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._check_settled)
        self._settle_target: Optional[Tuple[str, int, Optional[str]]] = None

    def current_index(self) -> int:
        return self._stack.current_index

    def current_subroute(self) -> Optional[str]:
        if self.current_index() != NavigationAdapter.ROUTE_MAP["workspace"]:
            return None
        dock = getattr(self._window, "generation_dock", None)
        drawer_anim = getattr(self._window, "drawer_anim", None)
        if dock is None or not dock.isVisible():
            return None
        if drawer_anim is not None and drawer_anim.state() == QAbstractAnimation.Running:
            return None
        return self.TAB_TO_SUBROUTE.get(self._window.dock_tabs.currentIndex())

    def navigate_to_index(self, index: int, subroute: Optional[str]) -> str:
        operation_id = f"op-{next(self._ids)}"
        self._active_operation_id = operation_id
        self._settle_timer.stop()
        self._settle_target = (operation_id, index, subroute)
        if index == NavigationAdapter.ROUTE_MAP["workspace"] and subroute in self.SUBROUTE_TO_TAB:
            self._window.dock_tabs.setCurrentIndex(self.SUBROUTE_TO_TAB[subroute])
            dock = getattr(self._window, "generation_dock", None)
            if dock is not None and not dock.isVisible():
                toggle = getattr(self._window, "_toggle_ai_drawer", None)
                if toggle is not None:
                    toggle()
                else:
                    dock.show()
        nav_index = self.INDEX_TO_NAV_INDEX.get(index)
        if nav_index is None:
            self._settle_target = None
            QTimer.singleShot(0, lambda: self.transition_failed.emit(operation_id, "Unknown index"))
        else:
            self._window.switch_page(nav_index)
            self._settle_timer.start(0)
        return operation_id

    def _on_transition_finished(self) -> None:
        if self._active_operation_id is None:
            return
        self._settle_timer.start(0)

    def _check_settled(self) -> None:
        if self._settle_target is None:
            return
        operation_id, index, subroute = self._settle_target
        if operation_id != self._active_operation_id:
            return
        drawer_anim = getattr(self._window, "drawer_anim", None)
        stack_animating = self._stack.anim_group.state() == QAbstractAnimation.Running
        drawer_animating = (
            drawer_anim is not None
            and drawer_anim.state() == QAbstractAnimation.Running
        )
        dock = getattr(self._window, "generation_dock", None)
        drawer_settled = subroute is None or (
            dock is not None
            and dock.isVisible()
            and not drawer_animating
            and self.TAB_TO_SUBROUTE.get(self._window.dock_tabs.currentIndex()) == subroute
        )
        if self.current_index() != index or stack_animating or not drawer_settled:
            self._settle_timer.start(50)
            return
        self._settle_target = None
        self._active_operation_id = None
        self.transition_finished.emit(operation_id, index)

    def cancel_operation(self) -> None:
        self._settle_timer.stop()
        self._settle_target = None
        self._active_operation_id = None
