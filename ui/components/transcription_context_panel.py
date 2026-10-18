import os

from PySide6.QtCore import QSignalBlocker, Qt, QThread, QTimer, Signal, Slot
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
from core.transcription.glossary_extractor import extract_glossary_from_summary
from core.translation.llm_translation_service import GeminiRESTProvider
from ui.theme import Theme


class _GlossaryExtractionWorker(QThread):
    extracted = Signal(object)
    failed = Signal(str)

    def __init__(self, provider_factory, summary: str, video_language: str, domain: str, parent=None):
        super().__init__(parent)
        self._provider_factory = provider_factory
        self._summary = summary
        self._video_language = video_language
        self._domain = domain

    def run(self):
        try:
            provider = self._provider_factory()
            terms = extract_glossary_from_summary(
                provider=provider,
                summary=self._summary,
                video_language=self._video_language,
                domain=self._domain,
            )
            self.extracted.emit(terms)
        except Exception as exc:
            self.failed.emit(str(exc))


class TranscriptionContextPanel(QWidget):
    context_committed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._llm_provider_factory = lambda: GeminiRESTProvider(
            api_key=os.environ.get("GEMINI_API_KEY", "")
        )
        self._language_getter = lambda: "Auto Detect"
        self._extraction_worker: _GlossaryExtractionWorker | None = None
        self._active_workers: set[_GlossaryExtractionWorker] = set()

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
            QPushButton {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.CYAN};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Theme.SURFACE_ELEVATED};
                border-color: {Theme.CYAN};
            }}
            QPushButton:disabled {{
                background-color: {Theme.BG_APP};
                color: {Theme.TEXT_DISABLED};
                border-color: {Theme.BORDER};
            }}
            """
        )
        self.context_edit = QPlainTextEdit()
        self.context_edit.setPlaceholderText("Context / Video summary for Whisper")
        self.glossary_edit = QPlainTextEdit()
        self.glossary_edit.setPlaceholderText(
            "One glossary term per line (e.g., Term or Source -> Target)"
        )
        self.diagnostics_label = QLabel("No prompt compiled")
        self.diagnostics_label.setWordWrap(True)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(400)

        layout = QVBoxLayout(self)
        context_header_row = QHBoxLayout()
        context_header_row.addWidget(QLabel("Transcription Context"))
        context_header_row.addStretch()
        self.btn_auto_glossary = QPushButton("✨ Auto Glossary")
        self.btn_auto_glossary.setCursor(Qt.PointingHandCursor)
        self.btn_auto_glossary.setToolTip(
            "Extract terminology from summary in the video's spoken language"
        )
        self.btn_auto_glossary.clicked.connect(self._extract_glossary_from_summary)
        context_header_row.addWidget(self.btn_auto_glossary)
        layout.addLayout(context_header_row)
        layout.addWidget(self.context_edit)

        glossary_header_row = QHBoxLayout()
        glossary_header_row.addWidget(QLabel("Glossary Terms"))
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
        self.btn_sync_db.setCursor(Qt.PointingHandCursor)
        self.btn_sync_db.setToolTip("Pull terms matching domain from Glossary DB")
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

    def set_llm_provider_factory(self, factory) -> None:
        self._llm_provider_factory = factory

    def set_language_getter(self, getter) -> None:
        self._language_getter = getter

    def _cleanup_worker(self, worker: _GlossaryExtractionWorker) -> None:
        self._active_workers.discard(worker)
        worker.deleteLater()

    def _reset_extraction_worker(self) -> None:
        worker = self._extraction_worker
        self._extraction_worker = None
        if worker is not None:
            try:
                worker.extracted.disconnect(self._on_glossary_extracted)
                worker.failed.disconnect(self._on_glossary_extraction_failed)
            except (RuntimeError, TypeError):
                pass
        self.btn_auto_glossary.setEnabled(True)
        self.btn_auto_glossary.setText("✨ Auto Glossary")

    def _extract_glossary_from_summary(self) -> None:
        summary = self.context_edit.toPlainText().strip()
        if not summary:
            self.diagnostics_label.setText(
                "⚠ Enter a video summary/context above before generating a glossary."
            )
            return
        if self._extraction_worker is not None and self._extraction_worker.isRunning():
            return

        video_language = (
            self._language_getter() if self._language_getter else "Auto Detect"
        ) or "Auto Detect"
        domain = self.domain_edit.text().strip() or "general"

        self.btn_auto_glossary.setEnabled(False)
        self.btn_auto_glossary.setText("⏳ Extracting...")
        self.diagnostics_label.setText(f"Extracting glossary ({video_language})...")

        worker = _GlossaryExtractionWorker(
            provider_factory=self._llm_provider_factory,
            summary=summary,
            video_language=video_language,
            domain=domain,
            parent=None,
        )
        self._active_workers.add(worker)
        self._extraction_worker = worker
        worker.extracted.connect(self._on_glossary_extracted, Qt.QueuedConnection)
        worker.failed.connect(self._on_glossary_extraction_failed, Qt.QueuedConnection)
        worker.finished.connect(
            lambda w=worker: self._cleanup_worker(w), Qt.QueuedConnection
        )
        worker.start()

    @Slot(object)
    def _on_glossary_extracted(self, extracted_terms: list[str]) -> None:
        if self._extraction_worker is None:
            return
        self._reset_extraction_worker()
        if not extracted_terms:
            self.diagnostics_label.setText("⚠ No glossary terms extracted from summary.")
            return

        existing = [
            line.strip()
            for line in self.glossary_edit.toPlainText().splitlines()
            if line.strip()
        ]
        existing_norm = TranscriptionContext(glossary=existing).normalized().glossary
        merged = TranscriptionContext(
            context=self.context_edit.toPlainText(),
            glossary=existing_norm + list(extracted_terms),
            domain=self.domain_edit.text().strip() or "general",
        ).normalized()
        added_count = len(merged.glossary) - len(existing_norm)
        self.diagnostics_label.setText(
            f"✓ Extracted {len(extracted_terms)} glossary term(s) ({added_count} new)"
        )

        self.debounce_timer.stop()
        blocker = QSignalBlocker(self.glossary_edit)
        self.glossary_edit.setPlainText("\n".join(merged.glossary))
        del blocker
        self._commit()

    @Slot(str)
    def _on_glossary_extraction_failed(self, error_msg: str) -> None:
        if self._extraction_worker is None:
            return
        self._reset_extraction_worker()
        self.diagnostics_label.setText(f"⚠ Auto Glossary failed: {error_msg}")

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
        self._reset_extraction_worker()
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
