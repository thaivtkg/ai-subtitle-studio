import uuid
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from .environment import TourEnvironment
from .models import (
    AnchorResolution,
    AnchorStatus,
    TargetPolicy,
    TourDefinition,
    TourState,
    TourStep,
    TourStepType,
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
        navigation: Optional[NavigationPort],
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

    def state(self) -> TourState:
        return self._state

    def current_step(self) -> Optional[TourStep]:
        if self._current_definition is None:
            return None
        if not 0 <= self._current_step_index < len(self._current_definition.steps):
            return None
        return self._current_definition.steps[self._current_step_index]

    def _transition_to(self, new_state: TourState) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(new_state)

    def _cleanup_step_scope(self) -> None:
        if self._interaction_observer.is_bound():
            self._interaction_observer.unbind()
        self._spotlight.hide_step()

    def start(self, guide_id: str) -> bool:
        if self._state is not TourState.IDLE:
            return False
        guide = self._catalog.get_guide(guide_id)
        if guide is None or not guide.steps:
            return False

        self._current_definition = guide
        self._current_step_index = 0
        self._session_id = str(uuid.uuid4())
        self._generation = 1
        self.tour_started.emit(guide_id)
        self._dialog_observer.start(self._session_id)
        self._process_current_step()
        return True

    def cancel(self, reason: str = "USER_CANCELLED") -> None:
        if self._state in {TourState.IDLE, TourState.COMPLETED, TourState.CANCELLED}:
            return
        self._cleanup_step_scope()
        self._dialog_observer.stop()
        self._spotlight.detach_host()
        session_id = self._session_id
        self._current_definition = None
        self._current_step_index = -1
        self._transition_to(TourState.CANCELLED)
        self.tour_cancelled.emit(session_id, reason)

    def back(self) -> None:
        step = self.current_step()
        if step is None or not step.safety.allow_back or self._current_step_index <= 0:
            return
        self._cleanup_step_scope()
        self._current_step_index -= 1
        self._generation += 1
        self._process_current_step()

    def _process_current_step(self) -> None:
        step = self.current_step()
        if step is None:
            self._transition_to(TourState.COMPLETED)
            if self._current_definition is not None:
                self.tour_completed.emit(self._current_definition.guide_id)
            return
        self._transition_to(TourState.PREPARING_SURFACE)
        self.step_changed.emit(
            self._session_id, step.step_id, self._current_step_index, self._generation
        )
        self._transition_to(TourState.RESOLVING_TARGET)
        self._resolve_target_and_present(step)

    def _resolve_target_and_present(self, step: TourStep) -> None:
        resolution = AnchorResolution(AnchorStatus.NOT_FOUND)
        if step.anchor:
            resolution = self._anchor_registry.resolve(step.anchor)
        if resolution.status is not AnchorStatus.RESOLVED:
            if step.target_policy is TargetPolicy.REQUIRED:
                self._transition_to(TourState.RECOVERING)
                self._spotlight.show_recovery(
                    "Không tìm thấy thành phần này.", retry_enabled=True, skip_enabled=True
                )
                return
            if step.target_policy is TargetPolicy.SKIP:
                self._transition_to(TourState.ADVANCING_STEP)
                self._cleanup_step_scope()
                self._current_step_index += 1
                self._generation += 1
                self._process_current_step()
                return

        if step.step_type is TourStepType.INFO:
            self._transition_to(TourState.SHOWING_INFO)
            if resolution.handle is not None:
                self._spotlight.show_target(resolution.handle, step.callout, None)
            else:
                self._spotlight.show_info_without_target(step.callout, None)
        elif step.step_type is TourStepType.ACTION:
            self._transition_to(TourState.WAITING_ACTION)
            if resolution.handle is not None:
                self._spotlight.show_target(resolution.handle, step.callout, None)
                if step.interaction is not None:
                    self._interaction_observer.bind(
                        resolution.handle,
                        step.interaction,
                        session_id=self._session_id,
                        generation=self._generation,
                    )
        elif step.step_type is TourStepType.DEMO:
            self._transition_to(TourState.SHOWING_DEMO)
            if step.demo is not None:
                self._spotlight.show_demo(step.demo, step.callout, None)

    def next(self) -> None:
        pass

    def skip_step(self) -> None:
        pass

    def retry(self) -> None:
        pass
