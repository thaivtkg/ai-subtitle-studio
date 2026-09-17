from collections import deque
from dataclasses import dataclass
from datetime import datetime
import re

import html

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ui.theme import Theme


MAX_ACTIVITY_LOG_ENTRIES = 2000

_LEVEL_PREFIX = re.compile(
    r"^\[(DEBUG|INFO|WARNING|ERROR)(?:-([^\]]+))?\]\s*(.*)$",
    re.IGNORECASE,
)
_SOURCE_PREFIX = re.compile(r"^\[([^\]]+)\]\s*(.*)$")

_SOURCE_ALIASES = {
    "TIMING": "TIMING",
    "QUEUE": "QUEUE",
    "AI": "AI",
    "FFMPEG": "FFMPEG",
    "SYNC": "SYNC",
    "HỆ THỐNG": "SYSTEM",
}


@dataclass(frozen=True)
class ActivityLogEntry:
    timestamp: datetime
    level: str
    source: str
    message: str
    raw_text: str | None = None


def parse_activity_log(raw) -> ActivityLogEntry:
    text = raw if isinstance(raw, str) else str(raw)
    match = _LEVEL_PREFIX.match(text)
    if match:
        level, source, message = match.groups()
        return ActivityLogEntry(
            timestamp=datetime.now(),
            level=level.upper(),
            source=(source or "SYSTEM").strip().upper(),
            message=message,
            raw_text=text,
        )

    match = _SOURCE_PREFIX.match(text)
    if match:
        raw_source, message = match.groups()
        source = _SOURCE_ALIASES.get(raw_source.strip().upper())
        if source:
            return ActivityLogEntry(
                timestamp=datetime.now(),
                level="INFO",
                source=source,
                message=message,
                raw_text=text,
            )

    return ActivityLogEntry(
        timestamp=datetime.now(),
        level="INFO",
        source="SYSTEM",
        message=text,
        raw_text=text,
    )


class ActivityLogModel:
    def __init__(self, max_entries: int = MAX_ACTIVITY_LOG_ENTRIES):
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries = deque(maxlen=max_entries)
        self._level_filter = "ALL"
        self._source_filter = "ALL"
        self.auto_scroll = True
        self._listeners = []

    @property
    def entries(self) -> tuple[ActivityLogEntry, ...]:
        return tuple(self._entries)

    @property
    def visible_entries(self) -> tuple[ActivityLogEntry, ...]:
        return tuple(entry for entry in self._entries if self._matches(entry))

    @property
    def level_filter(self) -> str:
        return self._level_filter

    @property
    def source_filter(self) -> str:
        return self._source_filter

    def append(self, value) -> ActivityLogEntry:
        if isinstance(value, str):
            entry = parse_activity_log(value)
        elif isinstance(value, ActivityLogEntry):
            entry = value
        else:
            raise TypeError("ActivityLogModel.append accepts str or ActivityLogEntry")
        evicted = len(self._entries) == self.max_entries
        self._entries.append(entry)
        self._notify("append", entry, evicted)
        return entry

    def clear(self) -> None:
        self._entries.clear()
        self._source_filter = "ALL"
        self._notify("clear", None, False)

    def set_level_filter(self, value) -> None:
        normalized = str(value or "ALL").strip().upper()
        self._level_filter = normalized if normalized in {"ALL", "DEBUG", "INFO", "WARNING", "ERROR"} else "ALL"
        self._notify("filter", None, False)

    def set_source_filter(self, value) -> None:
        normalized = str(value or "ALL").strip().upper()
        self._source_filter = normalized or "ALL"
        self._notify("filter", None, False)

    def set_auto_scroll(self, enabled: bool) -> None:
        self.auto_scroll = bool(enabled)
        self._notify("auto_scroll", None, False)

    def should_scroll_for(self, entry: ActivityLogEntry) -> bool:
        return self.auto_scroll and self._matches(entry)

    def _matches(self, entry: ActivityLogEntry) -> bool:
        return (
            (self._level_filter == "ALL" or entry.level == self._level_filter)
            and (self._source_filter == "ALL" or entry.source == self._source_filter)
        )

    def subscribe(self, callback) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, event, entry, evicted) -> None:
        for callback in tuple(self._listeners):
            callback(event, entry, evicted)


class ActivityLogView(QFrame):
    def __init__(self, model: ActivityLogModel, parent=None):
        super().__init__(parent)
        self.model = model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("📜 Activity Stream")
        title.setStyleSheet(
            f"font-weight: bold; font-size: 12px; color: {Theme.TEXT_MUTED}; border: none;"
        )
        header.addWidget(title)
        header.addStretch()

        self.level_filter = QComboBox()
        self.level_filter.addItems(["All", "Debug", "Info", "Warning", "Error"])
        self.level_filter.currentTextChanged.connect(self._on_level_filter_changed)
        header.addWidget(self.level_filter)

        self.source_filter = QComboBox()
        self.source_filter.addItem("All")
        self.source_filter.currentTextChanged.connect(self._on_source_filter_changed)
        header.addWidget(self.source_filter)

        self.auto_scroll_control = QCheckBox("Auto-scroll")
        self.auto_scroll_control.setChecked(True)
        self.auto_scroll_control.toggled.connect(self.model.set_auto_scroll)
        header.addWidget(self.auto_scroll_control)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Clear activity log")
        self.clear_button.clicked.connect(self.model.clear)
        header.addWidget(self.clear_button)
        layout.addLayout(header)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText("Hệ thống sẵn sàng...")
        layout.addWidget(self.text_edit)
        self.model.subscribe(self._on_model_changed)
        self._render()

    def _on_model_changed(self, event, entry, evicted):
        if event in {"append", "clear"}:
            self._refresh_sources()
        if event in {"filter", "clear"}:
            self._sync_filter_controls()
        elif event == "auto_scroll":
            self._sync_auto_scroll_control()
        if event == "append" and not evicted:
            if entry in self.model.visible_entries:
                self.text_edit.append(self._render_entry(entry))
                if self.model.should_scroll_for(entry):
                    scrollbar = self.text_edit.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
            return
        self._render(preserve_scroll=event == "filter")

    def _render(self, preserve_scroll=False):
        scrollbar = self.text_edit.verticalScrollBar()
        previous_value = scrollbar.value()
        self.text_edit.clear()
        for entry in self.model.visible_entries:
            self.text_edit.append(self._render_entry(entry))
        if preserve_scroll:
            scrollbar.setValue(min(previous_value, scrollbar.maximum()))

    def _on_level_filter_changed(self, value):
        self.model.set_level_filter(value)

    def _on_source_filter_changed(self, value):
        self.model.set_source_filter(value)

    def _sync_filter_controls(self):
        labels = {"ALL": "All", "DEBUG": "Debug", "INFO": "Info", "WARNING": "Warning", "ERROR": "Error"}
        self.level_filter.blockSignals(True)
        self.level_filter.setCurrentText(labels[self.model.level_filter])
        self.level_filter.blockSignals(False)
        self.source_filter.blockSignals(True)
        options = [self.source_filter.itemText(i) for i in range(self.source_filter.count())]
        selected = self.model.source_filter if self.model.source_filter in options else "ALL"
        self.source_filter.setCurrentText("All" if selected == "ALL" else selected)
        self.source_filter.blockSignals(False)

    def _sync_auto_scroll_control(self):
        self.auto_scroll_control.blockSignals(True)
        self.auto_scroll_control.setChecked(self.model.auto_scroll)
        self.auto_scroll_control.blockSignals(False)

    def _refresh_sources(self):
        current = self.model.source_filter
        sources = []
        for entry in self.model.entries:
            if entry.source not in sources:
                sources.append(entry.source)
        options = ["All", *sources]
        selected = current if current in options else "ALL"
        self.source_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItems(options)
        self.source_filter.setCurrentText("All" if selected == "ALL" else selected)
        self.source_filter.blockSignals(False)
        if selected != current:
            self.model.set_source_filter(selected)

    def toPlainText(self):
        return self.text_edit.toPlainText()

    def setPlaceholderText(self, text):
        self.text_edit.setPlaceholderText(text)

    def clear(self):
        self.model.clear()

    def verticalScrollBar(self):
        return self.text_edit.verticalScrollBar()

    @staticmethod
    def _render_entry(entry):
        timestamp = html.escape(entry.timestamp.strftime("%H:%M:%S"))
        level = html.escape(entry.level)
        source = html.escape(entry.source)
        message = html.escape(entry.message)
        level_color = {
            "DEBUG": Theme.TEXT_MUTED,
            "INFO": Theme.TEXT_PRIMARY,
            "WARNING": Theme.WARNING,
            "ERROR": Theme.DANGER,
        }.get(entry.level, Theme.TEXT_PRIMARY)
        return (
            f'<span style="color:{Theme.TEXT_MUTED}">{timestamp}</span> '
            f'<span style="color:{level_color}">{level}</span> '
            f'<span style="color:{Theme.CYAN}">{source}</span> '
            f'<span style="color:{Theme.TEXT_PRIMARY}">{message}</span>'
        )
