from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.tutorial.models import CalloutSpec
from ui.theme import Theme


class TourCalloutWidget(QWidget):
    """Small, self-contained callout used by the spotlight layer."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("tour_callout_widget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#tour_callout_widget {{ background-color: {Theme.SURFACE_ELEVATED}; border: 1px solid {Theme.CYAN}; "
            f"border-radius: 8px; }}"
            f"QLabel#callout_title {{ font-weight: bold; font-size: 14px; color: {Theme.TEXT_PRIMARY}; }}"
            f"QLabel#callout_body {{ font-size: 12px; color: {Theme.TEXT_SECONDARY}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        self.title_label = QLabel()
        self.title_label.setObjectName("callout_title")
        self.title_label.setWordWrap(True)
        self.body_label = QLabel()
        self.body_label.setObjectName("callout_body")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        layout.addLayout(self.button_layout)
        self.buttons: Dict[str, QPushButton] = {}

    def setup(
        self,
        callout: Optional[CalloutSpec],
        controls: Any,
        *,
        is_recovery: bool = False,
        retry_enabled: bool = False,
        skip_enabled: bool = False,
    ) -> None:
        self.title_label.setVisible(callout is not None)
        self.body_label.setVisible(callout is not None)
        if callout is not None:
            self.title_label.setText(callout.title)
            self.body_label.setText(callout.body)

        for button in self.buttons.values():
            button.deleteLater()
        self.buttons.clear()

        specs = []
        if is_recovery:
            if hasattr(controls, "cancel"):
                specs.append(("cancel", "End Tour", controls.cancel, False))
            if skip_enabled and hasattr(controls, "skip_step"):
                specs.append(("skip", "Skip Step", controls.skip_step, False))
            if retry_enabled and hasattr(controls, "retry"):
                specs.append(("retry", "Retry", controls.retry, True))
        else:
            if hasattr(controls, "cancel"):
                specs.append(("cancel", "End Tour", controls.cancel, False))
            if getattr(controls, "can_back", True) and hasattr(controls, "back"):
                specs.append(("back", "Back", controls.back, False))
            if getattr(controls, "can_skip", True) and hasattr(controls, "skip_step"):
                specs.append(("skip", "Skip", controls.skip_step, False))
            if getattr(controls, "can_next", True) and hasattr(controls, "next"):
                specs.append(("next", "Next", controls.next, True))

        for name, text, slot, primary in specs:
            button = QPushButton(text)
            if primary:
                button.setStyleSheet(f"background-color: {Theme.PRIMARY_PURPLE}; color: {Theme.TEXT_PRIMARY}; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
            else:
                button.setStyleSheet(f"background-color: transparent; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER}; padding: 6px 12px; border-radius: 4px;")
            button.clicked.connect(slot)
            self.button_layout.addWidget(button)
            self.buttons[name] = button

    def set_recovery_message(
        self, message: str, controls: Any, retry_enabled: bool, skip_enabled: bool
    ) -> None:
        self.setup(
            CalloutSpec("Navigation error", message),
            controls,
            is_recovery=True,
            retry_enabled=retry_enabled,
            skip_enabled=skip_enabled,
        )
