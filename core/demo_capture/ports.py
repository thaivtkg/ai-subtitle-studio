from typing import Any, Callable, Protocol

from core.demo_capture.models import CaptureAction, CaptureProfile


class TargetResolverPort(Protocol):
    def resolve_widget(self, semantic_id: str) -> Any:
        ...


class NavigationAdapterPort(Protocol):
    def navigate(self, destination: str) -> None:
        ...


EventPump = Callable[[], None]
Clock = Callable[[], float]
TickCallback = Callable[[], None]
