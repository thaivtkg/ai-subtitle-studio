from PySide6.QtCore import QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from core.project.transcription_context import TranscriptionContext


class TranscriptionContextPanel(QWidget):
    context_committed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context_edit = QPlainTextEdit()
        self.context_edit.setPlaceholderText("Context for Whisper")
        self.glossary_edit = QPlainTextEdit()
        self.glossary_edit.setPlaceholderText("One glossary term per line")
        self.diagnostics_label = QLabel("No prompt compiled")
        self.diagnostics_label.setWordWrap(True)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Transcription Context"))
        layout.addWidget(self.context_edit)
        layout.addWidget(QLabel("Glossary"))
        layout.addWidget(self.glossary_edit)
        row = QHBoxLayout()
        row.addWidget(QLabel("Prompt diagnostics:"))
        row.addWidget(self.diagnostics_label, stretch=1)
        layout.addLayout(row)
        self.context_edit.textChanged.connect(self._schedule_commit)
        self.glossary_edit.textChanged.connect(self._schedule_commit)
        self.debounce_timer.timeout.connect(self._commit)

    def _schedule_commit(self):
        self.debounce_timer.start()

    def _commit(self):
        glossary = [line.strip() for line in self.glossary_edit.toPlainText().splitlines()]
        self.context_committed.emit(
            TranscriptionContext(self.context_edit.toPlainText(), glossary).normalized()
        )

    def set_context(self, context: TranscriptionContext) -> None:
        self.debounce_timer.stop()
        blockers = (QSignalBlocker(self.context_edit), QSignalBlocker(self.glossary_edit))
        normalized = context.normalized()
        self.context_edit.setPlainText(normalized.context)
        self.glossary_edit.setPlainText("\n".join(normalized.glossary))
        del blockers

    def set_prompt_diagnostics(self, compiled) -> None:
        total_glossary = compiled.glossary_items_used + compiled.glossary_items_dropped
        text = (
            f"{compiled.glossary_items_used}/{total_glossary} glossary · "
            f"~{compiled.token_count}/{compiled.max_tokens} tokens"
        )
        if compiled.truncated:
            warnings = []
            if compiled.glossary_items_dropped:
                warnings.append(
                    f"{compiled.glossary_items_dropped} glossary term(s) omitted"
                )
            if compiled.context_truncated:
                warnings.append("Context truncated")
            text += f"\n⚠ {' · '.join(warnings)}"
        self.diagnostics_label.setText(text)
