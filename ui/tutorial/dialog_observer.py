import weakref
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal
from PySide6.QtWidgets import QDialog

import shiboken6


class DialogLifecycleObserver(QObject):
    """Track QDialog lifetime and modal nesting without polling."""

    dialog_shown = Signal(str)
    dialog_finished = Signal(str, int)
    dialog_destroyed = Signal(str)
    modal_active_changed = Signal(bool)
    dialog_accepted = Signal(str)
    dialog_rejected = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._session_id = ""
        self._is_active = False
        self._dialog_counter = 0
        self._dialog_stack: List[str] = []
        self._dialogs: Dict[str, weakref.ReferenceType[QDialog]] = {}
        self._widget_id_to_handle: Dict[int, str] = {}
        self._destroyed_connected: set[int] = set()
        self._connections: Dict[str, List[Tuple[object, object, str]]] = {}

    def start(self, session_id: str) -> None:
        self.stop()
        self._session_id = session_id
        self._is_active = True
        app = QCoreApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def stop(self) -> None:
        had_modal = bool(self._dialog_stack)
        app = QCoreApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        for connections in self._connections.values():
            for signal, slot, _kind in connections:
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self._connections.clear()
        self._dialog_stack.clear()
        self._dialogs.clear()
        self._widget_id_to_handle.clear()
        self._destroyed_connected.clear()
        self._is_active = False
        self._session_id = ""
        if had_modal:
            self.modal_active_changed.emit(False)

    def is_active(self) -> bool:
        return self._is_active

    def session_id(self) -> str:
        return self._session_id

    def active_modal_handle(self) -> Optional[str]:
        while self._dialog_stack:
            dialog_id = self._dialog_stack[-1]
            dialog = self.dialog_for_handle(dialog_id)
            if dialog is not None and dialog.isVisible():
                return dialog_id
            self._dialog_stack.pop()
        return None

    def has_active_dialog(self) -> bool:
        return self.active_modal_handle() is not None

    def active_dialog(self) -> Optional[QDialog]:
        handle = self.active_modal_handle()
        return self.dialog_for_handle(handle) if handle else None

    def dialog_for_handle(self, dialog_id: str) -> Optional[QDialog]:
        ref = self._dialogs.get(dialog_id)
        dialog = ref() if ref is not None else None
        if dialog is not None and shiboken6.isValid(dialog):
            return dialog
        return None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._is_active and event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            self._track_dialog(watched)
        return False

    def _connect(self, dialog_id: str, signal: object, slot: object, kind: str) -> None:
        try:
            signal.connect(slot)
        except (RuntimeError, TypeError):
            return
        self._connections.setdefault(dialog_id, []).append((signal, slot, kind))

    def _track_dialog(self, dialog: QDialog) -> None:
        widget_id = id(dialog)
        existing_id = self._widget_id_to_handle.get(widget_id)
        if existing_id is not None and existing_id in self._dialog_stack:
            return

        was_modal = bool(self._dialog_stack)
        if existing_id is None:
            self._dialog_counter += 1
            dialog_id = f"dlg-{self._dialog_counter}"
        else:
            dialog_id = existing_id
        self._widget_id_to_handle[widget_id] = dialog_id
        self._dialogs[dialog_id] = weakref.ref(dialog)
        self._dialog_stack.append(dialog_id)
        dialog_ref = weakref.ref(dialog)
        self._connect(
            dialog_id,
            dialog.finished,
            lambda result, ref=dialog_ref, handle=dialog_id: self._on_dialog_finished(ref, handle, result),
            "finished",
        )
        if widget_id not in self._destroyed_connected:
            self._connect(
                dialog_id,
                dialog.destroyed,
                lambda _object=None, handle=dialog_id, wid=widget_id: self._on_dialog_destroyed(handle, wid),
                "destroyed",
            )
            self._destroyed_connected.add(widget_id)
        self.dialog_shown.emit(dialog_id)
        if not was_modal:
            self.modal_active_changed.emit(True)

    def _disconnect_dialog(self, dialog_id: str) -> None:
        for signal, slot, _kind in self._connections.pop(dialog_id, []):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def _disconnect_finished(self, dialog_id: str) -> None:
        remaining = []
        for signal, slot, kind in self._connections.get(dialog_id, []):
            if kind == "finished":
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            else:
                remaining.append((signal, slot, kind))
        if remaining:
            self._connections[dialog_id] = remaining
        else:
            self._connections.pop(dialog_id, None)

    def _on_dialog_finished(
        self, dialog_ref: weakref.ReferenceType[QDialog], dialog_id: str, result: int
    ) -> None:
        was_modal = bool(self._dialog_stack)
        dialog = dialog_ref()
        self._dialog_stack = [handle for handle in self._dialog_stack if handle != dialog_id]
        self._dialogs.pop(dialog_id, None)
        self._disconnect_finished(dialog_id)

        result_code = int(result)
        self.dialog_finished.emit(dialog_id, result_code)
        if result_code == int(QDialog.DialogCode.Accepted):
            self.dialog_accepted.emit(dialog_id)
        else:
            self.dialog_rejected.emit(dialog_id)
        if was_modal and not self.has_active_dialog():
            self.modal_active_changed.emit(False)

    def _on_dialog_destroyed(self, dialog_id: str, widget_id: int) -> None:
        was_modal = self.has_active_dialog()
        self._dialog_stack = [handle for handle in self._dialog_stack if handle != dialog_id]
        self._dialogs.pop(dialog_id, None)
        self._widget_id_to_handle.pop(widget_id, None)
        self._destroyed_connected.discard(widget_id)
        # The sender is already being destroyed; dropping bookkeeping avoids
        # libpyside warnings from disconnecting a dead signal.
        self._connections.pop(dialog_id, None)
        self.dialog_destroyed.emit(dialog_id)
        if was_modal and not self.has_active_dialog():
            self.modal_active_changed.emit(False)
