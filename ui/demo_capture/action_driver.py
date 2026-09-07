from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import (
    CaptureAction, CaptureProfile, ClickAction, HoldAction, NavigateAction,
    SelectAction, SetTextAction, WaitHiddenAction, WaitSettledAction,
    WaitVisibleAction,
)
from core.demo_capture.ports import Clock, EventPump, NavigationAdapterPort, TargetResolverPort, TickCallback


class UIActionDriver:
    def __init__(self, resolver: TargetResolverPort, event_pump: EventPump, clock: Clock,
                 navigation: NavigationAdapterPort = None, capture_root: QWidget = None):
        self._resolver = resolver
        self._navigation = navigation
        self._event_pump = event_pump
        self._clock = clock
        self._capture_root = capture_root

    def execute(self, action: CaptureAction, profile: CaptureProfile, tick: TickCallback) -> None:
        if isinstance(action, WaitVisibleAction):
            self._wait_visible(action, profile, tick)
        elif isinstance(action, WaitHiddenAction):
            self._wait_hidden(action, profile, tick)
        elif isinstance(action, ClickAction):
            self._click(action)
        elif isinstance(action, NavigateAction):
            if self._navigation is None:
                raise CaptureRunError(CaptureErrorCode.NAVIGATION_FAILED,
                                      "Navigation adapter is not configured", target=action.destination)
            self._navigation.navigate(action.destination)
        elif isinstance(action, HoldAction):
            self._hold(action, tick)
        elif isinstance(action, SetTextAction):
            self._set_text(action)
        elif isinstance(action, SelectAction):
            self._select(action)
        elif isinstance(action, WaitSettledAction):
            self._wait_settled(action, profile, tick)
        else:
            raise NotImplementedError(f"Action type {type(action).__name__} not yet implemented")

    def _click(self, action: ClickAction) -> None:
        widget = self._resolver.resolve_widget(action.target)
        if hasattr(widget, "click"):
            widget.click()
        else:
            QTest.mouseClick(widget, Qt.MouseButton.LeftButton)

    def _set_text(self, action: SetTextAction) -> None:
        widget = self._resolver.resolve_widget(action.target)
        if isinstance(widget, (QLineEdit, QTextEdit)):
            widget.setText(action.text)
            return
        raise CaptureRunError(CaptureErrorCode.ACTION_FAILED, "Widget does not support setText", target=action.target)

    def _select(self, action: SelectAction) -> None:
        widget = self._resolver.resolve_widget(action.target)
        if not isinstance(widget, QComboBox):
            raise CaptureRunError(CaptureErrorCode.ACTION_FAILED, "Widget is not a QComboBox", target=action.target)
        index = widget.findData(action.option)
        if index == -1:
            index = widget.findText(action.option)
        if index == -1:
            raise CaptureRunError(CaptureErrorCode.ACTION_FAILED,
                                  f"Option '{action.option}' not found in data or text", target=action.target)
        widget.setCurrentIndex(index)

    def _hold(self, action: HoldAction, tick: TickCallback) -> None:
        start_time = self._clock()
        while True:
            self._event_pump()
            tick()
            if (self._clock() - start_time) * 1000 >= action.duration_ms:
                return

    def _wait_settled(self, action: WaitSettledAction, profile: CaptureProfile, tick: TickCallback) -> None:
        timeout_ms = action.timeout_ms if action.timeout_ms is not None else profile.default_wait_timeout_ms
        start_time = self._clock()
        stable_cycles = 0
        last_signature = None
        while True:
            self._event_pump()
            signature = self._get_structural_signature()
            if last_signature is not None and signature == last_signature:
                stable_cycles += 1
                if stable_cycles >= 3:
                    return
            else:
                stable_cycles = 0
                last_signature = signature
            tick()
            if (self._clock() - start_time) * 1000 >= timeout_ms:
                raise CaptureRunError(CaptureErrorCode.WAIT_TIMEOUT, "UI structural state did not settle")

    def _get_structural_signature(self):
        if self._capture_root is None:
            return 0

        def signature(widget: QWidget):
            geometry = widget.geometry()
            return (
                type(widget).__name__,
                widget.objectName(),
                widget.isVisible(),
                widget.isEnabled(),
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            )

        widgets = self._capture_root.findChildren(QWidget)
        return hash(tuple([signature(widget) for widget in widgets] + [signature(self._capture_root)]))

    def _wait_visible(self, action: WaitVisibleAction, profile: CaptureProfile, tick: TickCallback) -> None:
        timeout_ms = action.timeout_ms if action.timeout_ms is not None else profile.default_wait_timeout_ms
        start_time = self._clock()
        while True:
            self._event_pump()
            try:
                self._resolver.resolve_widget(action.target)
                return
            except CaptureRunError as error:
                if error.error_code not in (CaptureErrorCode.TARGET_NOT_FOUND, CaptureErrorCode.TARGET_NOT_VISIBLE):
                    raise
            tick()
            if (self._clock() - start_time) * 1000 >= timeout_ms:
                raise CaptureRunError(CaptureErrorCode.WAIT_TIMEOUT, "", target=action.target)

    def _wait_hidden(self, action: WaitHiddenAction, profile: CaptureProfile, tick: TickCallback) -> None:
        timeout_ms = action.timeout_ms if action.timeout_ms is not None else profile.default_wait_timeout_ms
        start_time = self._clock()
        while True:
            self._event_pump()
            try:
                self._resolver.resolve_widget(action.target)
            except CaptureRunError as error:
                if error.error_code in (CaptureErrorCode.TARGET_NOT_FOUND, CaptureErrorCode.TARGET_NOT_VISIBLE):
                    return
                raise
            tick()
            if (self._clock() - start_time) * 1000 >= timeout_ms:
                raise CaptureRunError(CaptureErrorCode.WAIT_TIMEOUT, "", target=action.target)
