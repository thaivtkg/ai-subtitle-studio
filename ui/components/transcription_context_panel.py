from PySide6.QtCore import QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.project.transcription_context import TranscriptionContext
from ui.theme import Theme


class TranscriptionContextPanel(QWidget):
    context_committed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {Theme.BG_APP};
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
            QPlainTextEdit:focus {{ border: 1px solid {Theme.PRIMARY_PURPLE}; }}
            QPlainTextEdit {{ selection-background-color: {Theme.PRIMARY_PURPLE}; }}
            """
        )
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

        glossary_header_row = QHBoxLayout()
        glossary_header_row.addWidget(QLabel("Glossary (Term or Source -> Target)"))
        glossary_header_row.addStretch()
        self.domain_edit = QLineEdit()
        self.domain_edit.setPlaceholderText("Domain: general")
        self.domain_edit.setFixedWidth(130)
        self.domain_edit.setStyleSheet(
            f"background-color: {Theme.SURFACE_ELEVATED}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 6px; font-size: 11px;"
        )
        glossary_header_row.addWidget(self.domain_edit)

        self.btn_sync_db = QPushButton("🔄 Sync DB")
        self.btn_sync_db.setToolTip("Pull terms matching domain from Glossary DB")
        self.btn_sync_db.setStyleSheet(
            f"background-color: {Theme.SURFACE_SOFT}; color: {Theme.CYAN}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: 600;"
        )
        self.btn_sync_db.clicked.connect(self._sync_from_glossary_db)
        glossary_header_row.addWidget(self.btn_sync_db)
        layout.addLayout(glossary_header_row)

        layout.addWidget(self.glossary_edit)
        row = QHBoxLayout()
        row.addWidget(QLabel("Prompt diagnostics:"))
        row.addWidget(self.diagnostics_label, stretch=1)
        layout.addLayout(row)
        self.context_edit.textChanged.connect(self._schedule_commit)
        self.glossary_edit.textChanged.connect(self._schedule_commit)
        self.domain_edit.textChanged.connect(self._schedule_commit)
        self.debounce_timer.timeout.connect(self._commit)

    def _sync_from_glossary_db(self):
        curr_domain = self.domain_edit.text().strip() or "general"
        raw_glossary = [line.strip() for line in self.glossary_edit.toPlainText().splitlines() if line.strip()]
        ctx = TranscriptionContext(
            context=self.context_edit.toPlainText(),
            glossary=raw_glossary,
            domain=curr_domain,
        )
        loaded = ctx.load_from_glossary_db()
        self.glossary_edit.setPlainText("\n".join(loaded.glossary))
        self._schedule_commit()

    def _schedule_commit(self):
        self.debounce_timer.start()

    def _commit(self):
        glossary = [line.strip() for line in self.glossary_edit.toPlainText().splitlines()]
        self.context_committed.emit(
            TranscriptionContext(
                self.context_edit.toPlainText(),
                glossary,
                domain=self.domain_edit.text().strip() or "general",
            ).normalized()
        )

    def set_context(self, context: TranscriptionContext) -> None:
        self.debounce_timer.stop()
        blockers = (
            QSignalBlocker(self.context_edit),
            QSignalBlocker(self.glossary_edit),
            QSignalBlocker(self.domain_edit),
        )
        normalized = context.normalized()
        self.context_edit.setPlainText(normalized.context)
        self.glossary_edit.setPlainText("\n".join(normalized.glossary))
        self.domain_edit.setText(normalized.domain if normalized.domain != "general" else "")
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
