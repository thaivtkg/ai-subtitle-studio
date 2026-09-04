import uuid
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

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


class TourEngine(QObject):
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

        for name, handler in (("surface_ready", self.on_surface_ready),
                              ("surface_failed", self.on_surface_failed)):
            signal = getattr(self._navigation, name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(handler)

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

    def _cleanup_step_scope(self) -> None:
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
        self._spotlight.show_recovery("Navigation Failed", retry_enabled=True, skip_enabled=True)

    def _resolve_target_and_present(self, step: TourStep) -> None:
        if not step.anchor:
            if step.step_type is TourStepType.INFO:
                self._set_state(TourState.SHOWING_INFO)
                self._spotlight.show_info_without_target(step.callout, None)
            elif step.step_type is TourStepType.DEMO:
                self._set_state(TourState.SHOWING_DEMO)
                if step.demo is not None:
                    self._spotlight.show_demo(step.demo, step.callout, None)
            else:
                self._set_state(TourState.RECOVERING)
                self._spotlight.show_recovery(
                    "Hành động yêu cầu mục tiêu nhưng không có.",
                    retry_enabled=False,
                    skip_enabled=True,
                )
            return

        resolution = AnchorResolution(AnchorStatus.NOT_FOUND)
        if step.anchor:
            resolution = self._anchor_registry.resolve(step.anchor)
        if resolution.status != AnchorStatus.RESOLVED:
            if step.target_policy is TargetPolicy.REQUIRED:
                self._set_state(TourState.RECOVERING)
                self._spotlight.show_recovery("Không tìm thấy thành phần này.", retry_enabled=True, skip_enabled=True)
            elif step.target_policy is TargetPolicy.SKIP:
                self._advance_current_step()
            else:
                self._set_state(TourState.SHOWING_INFO)
                self._spotlight.show_info_without_target(step.callout, None)
            return
        if step.step_type is TourStepType.INFO:
            self._set_state(TourState.SHOWING_INFO)
            self._spotlight.show_target(resolution.handle, step.callout, None)
        elif step.step_type is TourStepType.ACTION:
            self._set_state(TourState.WAITING_ACTION)
            self._spotlight.show_target(resolution.handle, step.callout, None)
            if step.interaction is not None:
                self._interaction_observer.bind(
                    resolution.handle, step.interaction,
                    session_id=self._session_id, generation=self._generation,
                )
        elif step.step_type is TourStepType.DEMO:
            self._set_state(TourState.SHOWING_DEMO)
            if step.demo is not None:
                self._spotlight.show_demo(step.demo, step.callout, None)
