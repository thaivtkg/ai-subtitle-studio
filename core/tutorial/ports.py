from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from .models import (
    AnchorHandle,
    AnchorResolution,
    CalloutSpec,
    DemoSpec,
    InteractionSpec,
    SurfaceSpec,
)


class NavigationAdapterPort(QObject):
    surface_ready = Signal(str, int, str)
    surface_failed = Signal(str, int, str, str)

    def navigate(self, surface: SurfaceSpec, *, session_id: str, generation: int, request_id: str) -> None:
        raise NotImplementedError

    def current_surface(self) -> SurfaceSpec:
        raise NotImplementedError

    def cancel_pending(self) -> None:
        raise NotImplementedError


class AnchorRegistryPort:
    def resolve(self, anchor_id: str) -> AnchorResolution:
        raise NotImplementedError


class InteractionObserverPort(QObject):
    action_satisfied = Signal(str, int)
    target_lost = Signal(str, int, str)

    def bind(self, anchor: AnchorHandle, interaction: InteractionSpec, *, session_id: str, generation: int) -> Any:
        raise NotImplementedError

    def unbind(self) -> None:
        raise NotImplementedError

    def is_bound(self) -> bool:
        raise NotImplementedError


class SpotlightLayerPort(QObject):
    next_requested = Signal()
    back_requested = Signal()
    skip_step_requested = Signal()
    cancel_requested = Signal()
    retry_requested = Signal()

    def attach_host(self, host: Any) -> bool:
        raise NotImplementedError

    def detach_host(self) -> None:
        raise NotImplementedError

    def show_target(self, anchor: AnchorHandle, callout: CalloutSpec, controls: Any) -> bool:
        raise NotImplementedError

    def show_info_without_target(self, callout: CalloutSpec, controls: Any) -> None:
        raise NotImplementedError

    def show_demo(self, demo: DemoSpec, callout: CalloutSpec, controls: Any) -> bool:
        raise NotImplementedError

    def show_recovery(self, message: str, *, retry_enabled: bool, skip_enabled: bool) -> None:
        raise NotImplementedError

    def hide_step(self) -> None:
        raise NotImplementedError


class DialogLifecycleObserverPort(QObject):
    dialog_shown = Signal(str)
    dialog_finished = Signal(str, int)
    dialog_destroyed = Signal(str)
    modal_active_changed = Signal(bool)

    def start(self, session_id: str) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def active_modal_handle(self) -> Optional[str]:
        raise NotImplementedError


class TourProgressStorePort:
    def is_completed(self, guide_id: str, content_version: int) -> bool:
        raise NotImplementedError

    def mark_completed(self, guide_id: str, content_version: int) -> None:
        raise NotImplementedError

    def mark_dismissed(self, guide_id: str, content_version: int) -> None:
        raise NotImplementedError
