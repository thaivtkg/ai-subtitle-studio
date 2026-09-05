import uuid
from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from .environment import TourEnvironment
from .models import (
    AnchorResolution,
    AnchorStatus,
    TargetPolicy,
    TourDefinition,
    TourStep,
    TourStepType,
    TourState,
)
from .ports import (
    AnchorRegistryPort,
    DialogObserverPort,
    InteractionObserverPort,
    NavigationPort,
    ProgressStorePort,
    SpotlightPort,
)


class TourControlsFacade:
    """Plain-Python command facade exposed to UI adapters."""

    def __init__(self, engine: "TourEngine"):
        self._engine = engine
    def next(self, *args: Any) -> None:
        self._engine.next()

    def back(self, *args: Any) -> None:
        self._engine.back()

    def skip_step(self, *args: Any) -> None:
        self._engine.skip_step()

    def cancel(self, *args: Any) -> None:
        self._engine.cancel("USER_CANCELLED")

    def retry(self, *args: Any) -> None:
        self._engine.retry()

    @property
    def can_next(self) -> bool:
        return self._engine.state() in (TourState.SHOWING_INFO, TourState.SHOWING_DEMO)

    @property
    def can_back(self) -> bool:
        if self._engine.state() == TourState.WAITING_ACTION:
            return False
        step = self._engine.current_step()
        return bool(step and step.safety.allow_back and self._engine._current_step_index > 0)

    @property
    def can_skip(self) -> bool:
        return True


class TourEngine(QObject):
    NAVIGATION_TIMEOUT_MS = 2500
    TARGET_SETTLE_TIMEOUT_MS = 750
    state_changed = Signal(object)
    tour_started = Signal(str)
    step_changed = Signal(str, str, int, int)
    tour_completed = Signal(str)
    tour_cancelled = Signal(str, str)

    def __init__(
        self,
        catalog: Any,
        anchor_registry: AnchorRegistryPort,
        navigation: NavigationPort,
        interaction_observer: InteractionObserverPort,
        spotlight: SpotlightPort,
        dialog_observer: DialogObserverPort,
        progress_store: Optional[ProgressStorePort],
        environment: TourEnvironment,
        parent: Optional[QObject] = None,
        navigation_timeout_ms: int = NAVIGATION_TIMEOUT_MS,
        target_settle_timeout_ms: int = TARGET_SETTLE_TIMEOUT_MS,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._anchor_registry = anchor_registry
        self._navigation = navigation
        self._interaction_observer = interaction_observer
        self._spotlight = spotlight
        self._dialog_observer = dialog_observer
        self._progress_store = progress_store
        self._environment = environment
        self._state = TourState.IDLE
        self._current_definition: Optional[TourDefinition] = None
        self._current_step_index = -1
        self._session_id = ""
        self._generation = 0
        self._current_nav_request_id = ""
        self._controls = TourControlsFacade(self)
        self.nav_timeout_ms = navigation_timeout_ms
        self.settle_timeout_ms = target_settle_timeout_ms

        for name, handler in (("surface_ready", self.on_surface_ready),
                              ("surface_failed", self.on_surface_failed)):
            signal = getattr(self._navigation, name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(handler)
        action_signal = getattr(self._interaction_observer, "action_satisfied", None)
        if action_signal is not None and hasattr(action_signal, "connect"):
            action_signal.connect(self.on_action_satisfied)
        target_lost_signal = getattr(self._interaction_observer, "target_lost", None)
        if target_lost_signal is not None and hasattr(target_lost_signal, "connect"):
            target_lost_signal.connect(self.on_target_lost)

    def state(self) -> TourState:
        return self._state

    def is_running(self) -> bool:
        return self._state not in (TourState.IDLE, TourState.COMPLETED, TourState.CANCELLED)

    def current_step(self) -> Optional[TourStep]:
        if self._current_definition is None or self._current_step_index < 0:
            return None
        if self._current_step_index >= len(self._current_definition.steps):
            return None
        return self._current_definition.steps[self._current_step_index]

    def _set_state(self, state: TourState) -> None:
        if self._state != state:
            self._state = state
            self.state_changed.emit(state)

    def _cleanup_step_scope(self, observer_already_unbound: bool = False) -> None:
        if not observer_already_unbound:
            self._interaction_observer.unbind()
        self._navigation.cancel_pending()
        self._current_nav_request_id = ""
        self._spotlight.hide_step()

    def start(self, guide_id: str) -> bool:
        if self.is_running():
            return False
        guide = self._catalog.get_guide(guide_id)
        if guide is None or not guide.steps:
            return False
        if any(not self._environment.check(precondition) for precondition in guide.preconditions):
            return False

        self._current_definition = guide
        self._current_step_index = 0
        self._session_id = str(uuid.uuid4())
        self._generation = 1
        self._current_nav_request_id = ""
        self._dialog_observer.start(self._session_id)
        self.tour_started.emit(guide_id)
        self._process_current_step()
        return True

    def cancel(self, reason: str = "USER_CANCELLED") -> None:
        if not self.is_running():
            return
        session_id = self._session_id
        self._session_id = ""
        self._generation += 1
        self._current_nav_request_id = ""
        self._cleanup_step_scope()
        self._dialog_observer.stop()
        self._spotlight.detach_host()
        self._current_definition = None
        self._current_step_index = -1
        self._set_state(TourState.CANCELLED)
        self.tour_cancelled.emit(session_id, reason)

    def _complete_tour(self) -> None:
        guide = self._current_definition
        guide_id = guide.guide_id if guide else ""
        self._session_id = ""
        self._generation += 1
        self._current_nav_request_id = ""
        self._cleanup_step_scope()
        self._dialog_observer.stop()
        self._spotlight.detach_host()
        if guide is not None and self._progress_store is not None:
            self._progress_store.mark_completed(guide.guide_id, guide.content_version)
        self._current_definition = None
        self._current_step_index = -1
        self._set_state(TourState.COMPLETED)
        self.tour_completed.emit(guide_id)

    def next(self) -> None:
        if self._state in (TourState.SHOWING_INFO, TourState.SHOWING_DEMO):
            self._advance_current_step()

    def skip_step(self) -> None:
        step = self.current_step()
        if self.is_running() and step is not None and step.safety.allow_skip_step:
            self._advance_current_step()

    def back(self) -> None:
        step = self.current_step()
        if not self.is_running() or step is None or not step.safety.allow_back:
            return
        if self._current_step_index > 0:
            self._cleanup_step_scope()
            self._current_step_index -= 1
            self._generation += 1
            self._process_current_step()

    def retry(self) -> None:
        if self._state != TourState.RECOVERING or self.current_step() is None:
            return
        self._cleanup_step_scope()
        self._generation += 1
        self._process_current_step()

    def _advance_current_step(self) -> None:
        self._set_state(TourState.ADVANCING_STEP)
        self._cleanup_step_scope()
        self._current_step_index += 1
        self._generation += 1
        self._process_current_step()

    def _process_current_step(self) -> None:
        step = self.current_step()
        if step is None:
            self._complete_tour()
            return
        self._set_state(TourState.PREPARING_SURFACE)
        self.step_changed.emit(self._session_id, step.step_id, self._current_step_index, self._generation)
        if step.surface is not None:
            self._current_nav_request_id = str(uuid.uuid4())
            session_id = self._session_id
            generation = self._generation
            request_id = self._current_nav_request_id
            QTimer.singleShot(
                self.nav_timeout_ms,
                lambda s=session_id, g=generation, r=request_id: self._on_nav_timeout(s, g, r),
            )
            self._navigation.navigate(
                step.surface,
                session_id=self._session_id,
                generation=self._generation,
                request_id=self._current_nav_request_id,
            )
            return
        self._set_state(TourState.RESOLVING_TARGET)
        self._resolve_target_and_present(step)

    def _valid_navigation_signal(self, session_id: str, generation: int, request_id: str) -> bool:
        return (self._state == TourState.PREPARING_SURFACE
                and session_id == self._session_id
                and generation == self._generation
                and request_id == self._current_nav_request_id)

    def _on_nav_timeout(self, session_id: str, generation: int, request_id: str) -> None:
        if not self._valid_navigation_signal(session_id, generation, request_id):
            return
        self._current_nav_request_id = ""
        self._navigation.cancel_pending()
        self._set_state(TourState.RECOVERING)
        self._spotlight.show_recovery("Navigation Timeout", retry_enabled=True, skip_enabled=True, controls=self._controls)

    def on_surface_ready(self, session_id: str, generation: int, request_id: str) -> None:
        if not self._valid_navigation_signal(session_id, generation, request_id):
            return
        self._current_nav_request_id = ""
        self._set_state(TourState.RESOLVING_TARGET)
        step = self.current_step()
        if step is not None:
            self._resolve_target_and_present(step)

    def on_surface_failed(self, session_id: str, generation: int, request_id: str, reason: str) -> None:
        if not self._valid_navigation_signal(session_id, generation, request_id):
            return
        self._current_nav_request_id = ""
        self._set_state(TourState.RECOVERING)
        self._spotlight.show_recovery("Navigation Failed", retry_enabled=True, skip_enabled=True, controls=self._controls)

    def on_action_satisfied(self, session_id: str, generation: int) -> None:
        if (session_id != self._session_id or generation != self._generation
                or self._state != TourState.WAITING_ACTION):
            return
        if self._interaction_observer.is_bound():
            self._interaction_observer.unbind()
        self._set_state(TourState.ADVANCING_STEP)
        self._cleanup_step_scope(observer_already_unbound=True)
        self._generation += 1
        new_generation = self._generation
        QTimer.singleShot(
            0, lambda: self._queued_advance(session_id, new_generation)
        )

    def _queued_advance(self, session_id: str, new_generation: int) -> None:
        if (session_id != self._session_id or new_generation != self._generation
                or self._state != TourState.ADVANCING_STEP):
            return
        self._current_step_index += 1
        self._process_current_step()

    def _resolve_target_and_present(self, step: TourStep) -> None:
        if not step.anchor:
            if step.step_type is TourStepType.INFO:
                self._set_state(TourState.SHOWING_INFO)
                self._spotlight.show_info_without_target(step.callout, self._controls)
            elif step.step_type is TourStepType.DEMO:
                self._set_state(TourState.SHOWING_DEMO)
                if step.demo is not None:
                    self._spotlight.show_demo(step.demo, step.callout, self._controls)
            else:
                self._set_state(TourState.RECOVERING)
                self._spotlight.show_recovery(
                    "Hành động yêu cầu mục tiêu nhưng không có.",
                    retry_enabled=False,
                    skip_enabled=True,
                    controls=self._controls,
                )
            return

        resolution = self._anchor_registry.resolve(step.anchor)
        if resolution.status != AnchorStatus.RESOLVED:
            session_id = self._session_id
            generation = self._generation
            QTimer.singleShot(
                self.settle_timeout_ms,
                lambda s=session_id, g=generation: self._on_target_settle_timeout(s, g),
            )
            return
        self._present_resolved_target(step, resolution)

    def _on_target_settle_timeout(self, session_id: str, generation: int) -> None:
        if (session_id != self._session_id or generation != self._generation
                or self._state != TourState.RESOLVING_TARGET):
            return
        step = self.current_step()
        if step is None or step.anchor is None:
            return
        resolution = self._anchor_registry.resolve(step.anchor)
        if resolution.status is AnchorStatus.RESOLVED:
            self._present_resolved_target(step, resolution)
        else:
            self._apply_missing_target_policy(step)

    def on_target_lost(self, session_id: str, generation: int, reason: str) -> None:
        if (session_id != self._session_id or generation != self._generation
                or self._state not in (TourState.SHOWING_INFO, TourState.WAITING_ACTION,
                                       TourState.SHOWING_DEMO)):
            return
        step = self.current_step()
        if step is None:
            return
        self._cleanup_step_scope()
        self._apply_missing_target_policy(step)

    def _apply_missing_target_policy(self, step: TourStep) -> None:
        if step.target_policy is TargetPolicy.REQUIRED:
            self._set_state(TourState.RECOVERING)
            self._spotlight.show_recovery("Không tìm thấy thành phần này.", retry_enabled=True, skip_enabled=True, controls=self._controls)
        elif step.target_policy is TargetPolicy.SKIP:
            self._advance_current_step()
        else:
            self._set_state(TourState.SHOWING_INFO)
            self._spotlight.show_info_without_target(step.callout, self._controls)

    def _present_resolved_target(self, step: TourStep, resolution: AnchorResolution) -> None:
        if step.step_type is TourStepType.INFO:
            self._set_state(TourState.SHOWING_INFO)
            self._spotlight.show_target(resolution.handle, step.callout, self._controls)
        elif step.step_type is TourStepType.ACTION:
            self._set_state(TourState.WAITING_ACTION)
            self._spotlight.show_target(resolution.handle, step.callout, self._controls)
            if step.interaction is not None:
                self._interaction_observer.bind(
                    resolution.handle, step.interaction,
                    session_id=self._session_id, generation=self._generation,
                )
        elif step.step_type is TourStepType.DEMO:
            self._set_state(TourState.SHOWING_DEMO)
            if step.demo is not None:
                self._spotlight.show_demo(step.demo, step.callout, self._controls)
