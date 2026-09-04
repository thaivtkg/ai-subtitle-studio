import weakref
from typing import Any, Optional

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QWidget

from core.tutorial.models import AnchorHandle, InteractionSpec
from ui.tutorial.anchor_registry import AnchorRegistry


class InteractionObserverAdapter(QObject):
    """Observe one anchor's interaction without consuming its Qt events."""

    action_satisfied = Signal(str, int)
    target_lost = Signal(str, int, str)

    def __init__(self, registry: AnchorRegistry, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._registry = registry
        self._bound_widget_ref: Optional[weakref.ReferenceType[QWidget]] = None
        self._session_id = ""
        self._generation = 0
        self._interaction: Optional[InteractionSpec] = None

    def bind(
        self,
        anchor: AnchorHandle,
        interaction: InteractionSpec,
        *,
        session_id: str,
        generation: int,
    ) -> Any:
        self.unbind()
        widget = self._registry.get_widget(anchor)
        if widget is None or not shiboken6.isValid(widget):
            self.target_lost.emit(session_id, generation, "Target widget not found or invalid")
            return None

        self._bound_widget_ref = weakref.ref(widget)
        self._session_id = session_id
        self._generation = generation
        self._interaction = interaction
        widget.installEventFilter(self)
        widget.destroyed.connect(self._on_widget_destroyed)
        return None

    def unbind(self) -> None:
        widget_ref = self._bound_widget_ref
        self._bound_widget_ref = None
        self._session_id = ""
        self._generation = 0
        self._interaction = None
        if widget_ref is None:
            return

        widget = widget_ref()
        if widget is None or not shiboken6.isValid(widget):
            return
        widget.removeEventFilter(self)
        try:
            widget.destroyed.disconnect(self._on_widget_destroyed)
        except (RuntimeError, TypeError):
            pass

    def is_bound(self) -> bool:
        return self._bound_widget_ref is not None

    def _on_widget_destroyed(self, _object: Optional[QObject] = None) -> None:
        session_id, generation = self._session_id, self._generation
        self.unbind()
        if session_id:
            self.target_lost.emit(
                session_id, generation, "Target widget destroyed by application"
            )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        widget_ref = self._bound_widget_ref
        widget = widget_ref() if widget_ref else None
        if widget is None or not shiboken6.isValid(widget):
            return False
        if obj is widget and self._interaction and self._match_event(
            event, self._interaction.kind
        ):
            self.action_satisfied.emit(self._session_id, self._generation)
        return False

    @staticmethod
    def _match_event(event: QEvent, interaction_kind: Any) -> bool:
        kind = getattr(interaction_kind, "value", interaction_kind)
        kind = str(kind).lower()
        if kind == "click":
            return (
                event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton
            )
        if kind in {"input", "type", "text_committed"}:
            return event.type() == QEvent.Type.KeyPress
        if kind in {"hover", "enter"}:
            return event.type() == QEvent.Type.Enter
        if kind == "focus":
            return event.type() == QEvent.Type.FocusIn
        return False
