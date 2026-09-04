import weakref
from typing import Dict, List, Optional, Tuple

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal
from PySide6.QtWidgets import QDialog


class DialogLifecycleObserver(QObject):
    """Track visible dialogs through application Show/finished/destroyed events."""

    dialog_opened = Signal(object)
    dialog_closed = Signal(object, int)
    dialog_accepted = Signal(object)
    dialog_rejected = Signal(object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._session_id = ""
        self._is_active = False
        self._dialog_stack: List[weakref.ReferenceType[QDialog]] = []
        self._tracked_ids: set[int] = set()
        self._connections: Dict[int, List[Tuple[object, object]]] = {}

    def start(self, session_id: str) -> None:
        self.stop()
        self._session_id = session_id
        self._is_active = True
        app = QCoreApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def stop(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        for connections in self._connections.values():
            for signal, slot in connections:
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self._connections.clear()
        self._dialog_stack.clear()
        self._tracked_ids.clear()
        self._is_active = False
        self._session_id = ""

    def is_active(self) -> bool:
        return self._is_active

    def session_id(self) -> str:
        return self._session_id

    def active_dialog(self) -> Optional[QDialog]:
        while self._dialog_stack:
            dialog = self._dialog_stack[-1]()
            if dialog is not None and shiboken6.isValid(dialog) and dialog.isVisible():
                return dialog
            self._dialog_stack.pop()
        return None

    def has_active_dialog(self) -> bool:
        return self.active_dialog() is not None

    def active_modal_handle(self) -> Optional[str]:
        dialog = self.active_dialog()
        return dialog.objectName() if dialog is not None else None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._is_active and event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            self._track_dialog(watched)
        return False

    def _connect(self, dialog_id: int, signal: object, slot: object) -> None:
        try:
            signal.connect(slot)
        except (RuntimeError, TypeError):
            return
        self._connections.setdefault(dialog_id, []).append((signal, slot))

    def _track_dialog(self, dialog: QDialog) -> None:
        dialog_id = id(dialog)
        if dialog_id in self._tracked_ids:
            return
        self._tracked_ids.add(dialog_id)
        self._dialog_stack.append(weakref.ref(dialog))
        dialog_ref = weakref.ref(dialog)
        self._connect(
            dialog_id,
            dialog.finished,
            lambda result, ref=dialog_ref: self._on_dialog_finished(ref, result),
        )
        self._connect(
            dialog_id,
            dialog.destroyed,
            lambda _object=None, tracked_id=dialog_id: self._on_dialog_destroyed(tracked_id),
        )
        self.dialog_opened.emit(dialog)

    def _disconnect_dialog(self, dialog_id: int) -> None:
        for signal, slot in self._connections.pop(dialog_id, []):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def _remove_from_stack(self, dialog_id: int) -> None:
        self._dialog_stack = [
            ref for ref in self._dialog_stack
            if id(ref()) != dialog_id
        ]

    def _on_dialog_finished(
        self, dialog_ref: weakref.ReferenceType[QDialog], result: int
    ) -> None:
        dialog = dialog_ref()
        dialog_id = id(dialog) if dialog is not None else None
        if dialog_id is not None:
            self._tracked_ids.discard(dialog_id)
            self._remove_from_stack(dialog_id)
            self._disconnect_dialog(dialog_id)
        if dialog is None or not shiboken6.isValid(dialog):
            return
        result_code = int(result)
        self.dialog_closed.emit(dialog, result_code)
        if result_code == int(QDialog.DialogCode.Accepted):
            self.dialog_accepted.emit(dialog)
        else:
            self.dialog_rejected.emit(dialog)

    def _on_dialog_destroyed(self, dialog_id: int) -> None:
        self._tracked_ids.discard(dialog_id)
        self._disconnect_dialog(dialog_id)
        self._dialog_stack = [
            ref for ref in self._dialog_stack
            if id(ref()) != dialog_id
            and ref() is not None
            and shiboken6.isValid(ref())
        ]
