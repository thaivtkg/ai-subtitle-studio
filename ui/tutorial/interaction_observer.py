import weakref
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QWidget

import shiboken6

from core.tutorial.models import AnchorHandle, InteractionKind, InteractionSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.dialog_observer import DialogLifecycleObserver


class InteractionObserverAdapter(QObject):
    """Observe one anchor's interaction without consuming its Qt events."""

    action_satisfied = Signal(str, int)
    target_lost = Signal(str, int, str)

    def __init__(
        self,
        registry: AnchorRegistry,
        dialog_observer: Optional[DialogLifecycleObserver] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._registry = registry
        self._dialog_observer = dialog_observer
        self._bound_widget_ref: Optional[weakref.ReferenceType[QWidget]] = None
        self._session_id = ""
        self._generation = 0
        self._interaction_kind: Optional[InteractionKind] = None
        self._signal_connections: List[Tuple[Any, Any]] = []
        self._has_semantic_signal = False

    @staticmethod
    def _normalize_kind(interaction: InteractionSpec) -> InteractionKind:
        kind = interaction.kind
        if not isinstance(kind, InteractionKind):
            raise ValueError(f"Invalid interaction kind: {kind!r}")
        return kind

    def _connect_signal(self, signal: Any, slot: Any) -> bool:
        try:
            signal.connect(slot)
        except (RuntimeError, TypeError):
            return False
        self._signal_connections.append((signal, slot))
        return True

    def bind(
        self,
        anchor: AnchorHandle,
        interaction: InteractionSpec,
        *,
        session_id: str,
        generation: int,
    ) -> Any:
        self.unbind()
        kind = self._normalize_kind(interaction)
        widget = self._registry.get_widget(anchor)
        if widget is None or not shiboken6.isValid(widget):
            self.target_lost.emit(session_id, generation, "Target widget not found or invalid")
            return None

        self._bound_widget_ref = weakref.ref(widget)
        self._session_id = session_id
        self._generation = generation
        self._interaction_kind = kind
        widget.installEventFilter(self)
        self._connect_signal(widget.destroyed, self._on_widget_destroyed)
        if kind is InteractionKind.DIALOG_ACCEPTED:
            dialog = widget if isinstance(widget, QDialog) else widget.window()
            if not isinstance(dialog, QDialog) or not shiboken6.isValid(dialog):
                self.unbind()
                self.target_lost.emit(
                    session_id, generation,
                    "INTERACTION_BIND_FAILED: Target is not an observable dialog",
                )
                return None
            accepted = getattr(dialog, "accepted", None)
            if accepted is None or not self._connect_signal(accepted, self._on_semantic_action):
                if self._dialog_observer is None or not self._connect_signal(
                    self._dialog_observer.dialog_accepted, self._on_semantic_action
                ):
                    self.unbind()
                    self.target_lost.emit(
                        session_id,
                        generation,
                        "INTERACTION_BIND_FAILED: Dialog has no accepted signal",
                    )
                    return None
            self._connect_signal(dialog.finished, self._on_dialog_finished)
            return None

        # A target inside a dialog must not leave WAITING_ACTION when its window closes.
        window = widget.window()
        if isinstance(window, QDialog):
            self._connect_signal(window.finished, self._on_target_window_finished)
        if kind is InteractionKind.TEXT_COMMITTED:
            signal = getattr(widget, "editingFinished", None)
            if signal is None:
                signal = getattr(widget, "returnPressed", None)
            if signal is None or not self._connect_signal(signal, self._on_semantic_action):
                self.unbind()
                self.target_lost.emit(
                    session_id, generation,
                    "INTERACTION_BIND_FAILED: Widget does not support text commit signals",
                )
                return None
        if kind is InteractionKind.SELECTION_CHANGED:
            bound_signal = False
            for name in ("currentIndexChanged", "itemSelectionChanged", "selectionChanged"):
                signal = getattr(widget, name, None)
                if signal is not None:
                    bound_signal = self._connect_signal(signal, self._on_semantic_action)
                    if bound_signal:
                        break
            if not bound_signal:
                self.unbind()
                self.target_lost.emit(
                    session_id, generation,
                    "INTERACTION_BIND_FAILED: Widget does not support selection signals",
                )
                return None
        return None

    def unbind(self) -> None:
        widget_ref = self._bound_widget_ref
        self._bound_widget_ref = None
        self._session_id = ""
        self._generation = 0
        self._interaction_kind = None
        self._has_semantic_signal = False
        widget = widget_ref() if widget_ref is not None else None
        if widget is not None and shiboken6.isValid(widget):
            widget.removeEventFilter(self)
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._signal_connections.clear()

    def is_bound(self) -> bool:
        return self._bound_widget_ref is not None

    def _on_widget_destroyed(self, _object: Optional[QObject] = None) -> None:
        session_id, generation = self._session_id, self._generation
        self.unbind()
        self.target_lost.emit(
            session_id, generation, "Target widget destroyed by application"
        )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        widget_ref = self._bound_widget_ref
        widget = widget_ref() if widget_ref else None
        if widget is None or not shiboken6.isValid(widget):
            return False
        if obj is widget and self._interaction_kind is not None:
            if self._interaction_kind is InteractionKind.CLICK:
                matched = (
                    event.type() == QEvent.Type.MouseButtonRelease
                    and event.button() == Qt.MouseButton.LeftButton
                )
            elif self._interaction_kind is InteractionKind.FOCUS:
                matched = event.type() == QEvent.Type.FocusIn
            elif self._interaction_kind is InteractionKind.TEXT_COMMITTED:
                matched = False
            else:
                matched = False
            if matched:
                self.action_satisfied.emit(self._session_id, self._generation)
        return False

    def _on_semantic_action(self, *args: Any) -> None:
        if self._bound_widget_ref is not None and self._session_id:
            self.action_satisfied.emit(self._session_id, self._generation)

    def _on_dialog_finished(self, result: int) -> None:
        if self._interaction_kind is not InteractionKind.DIALOG_ACCEPTED:
            return
        if int(result) == int(QDialog.DialogCode.Accepted):
            return
        session_id, generation = self._session_id, self._generation
        self.unbind()
        self.target_lost.emit(
            session_id,
            generation,
            f"DIALOG_CLOSED_WITHOUT_ACCEPT: result={int(result)}",
        )

    def _on_target_window_finished(self, result: int) -> None:
        if not self._session_id:
            return
        session_id, generation = self._session_id, self._generation
        self.unbind()
        self.target_lost.emit(
            session_id,
            generation,
            f"TARGET_WINDOW_CLOSED: result={int(result)}",
        )
