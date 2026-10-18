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
            provider = self._provider_factory() if self._provider_factory else None
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
        self._llm_provider_factory = lambda: None
        self._language_getter = lambda: "Auto Detect"
        self._extraction_worker: _GlossaryExtractionWorker | None = None
        self._active_workers: set[_GlossaryExtractionWorker] = set()
        self._last_extracted_key: tuple[str, str, str] | None = None
        self._last_diagnostics_text: str | None = None
        self._auto_managed_terms: set[str] = set()

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
            QPushButton#AutoGlossaryToggle:checked {{
                background-color: {Theme.SURFACE_SOFT};
                color: {Theme.CYAN};
                border: 1px solid {Theme.CYAN};
            }}
            QPushButton#AutoGlossaryToggle:!checked {{
                background-color: {Theme.BG_APP};
                color: {Theme.TEXT_MUTED};
                border: 1px solid {Theme.BORDER};
            }}
            QPushButton:hover, QPushButton#AutoGlossaryToggle:hover {{
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

        self.auto_glossary_timer = QTimer(self)
        self.auto_glossary_timer.setSingleShot(True)
        self.auto_glossary_timer.setInterval(2000)

        layout = QVBoxLayout(self)
        context_header_row = QHBoxLayout()
        context_header_row.addWidget(QLabel("Transcription Context"))
        context_header_row.addStretch()
        self.btn_auto_glossary = QPushButton("✨ Auto Glossary: ON")
        self.btn_auto_glossary.setObjectName("AutoGlossaryToggle")
        self.btn_auto_glossary.setCheckable(True)
        self.btn_auto_glossary.setChecked(True)
        self.btn_auto_glossary.setCursor(Qt.PointingHandCursor)
        self.btn_auto_glossary.setToolTip(
            "When ON, automatically extracts terminology offline 2s after typing video summary"
        )
        self.btn_auto_glossary.toggled.connect(self._on_auto_glossary_toggled)
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
        self.context_edit.textChanged.connect(self._on_summary_or_domain_edited)
        self.glossary_edit.textChanged.connect(self._schedule_commit)
        self.domain_edit.textChanged.connect(self._on_summary_or_domain_edited)
        self.debounce_timer.timeout.connect(self._commit)
        self.auto_glossary_timer.timeout.connect(self._extract_glossary_from_summary)

    def set_llm_provider_factory(self, factory) -> None:
        self._llm_provider_factory = factory

    def set_language_getter(self, getter) -> None:
        self._language_getter = getter

    @Slot(str)
    def on_video_language_changed(self, _language: str = "") -> None:
        self.auto_glossary_timer.stop()
        self._reset_extraction_worker()
        self._extract_glossary_from_summary()

    def _update_auto_glossary_button_text(self, *, extracting: bool = False) -> None:
        if extracting and self.btn_auto_glossary.isChecked():
            self.btn_auto_glossary.setText("⏳ Auto Glossary...")
            return
        state = "ON" if self.btn_auto_glossary.isChecked() else "OFF"
        self.btn_auto_glossary.setText(f"✨ Auto Glossary: {state}")

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
            if self.diagnostics_label.text().startswith("Extracting glossary"):
                self.diagnostics_label.setText(
                    "Auto Glossary: OFF"
                    if not self.btn_auto_glossary.isChecked()
                    else (self._last_diagnostics_text or "Ready")
                )
        self._update_auto_glossary_button_text(extracting=False)

    def _schedule_auto_glossary(self) -> None:
        if not self.btn_auto_glossary.isChecked():
            self.auto_glossary_timer.stop()
            return
        if self.context_edit.toPlainText().strip():
            self.auto_glossary_timer.start()
        else:
            self.auto_glossary_timer.stop()
            self._last_extracted_key = None
            if self._auto_managed_terms:
                self._apply_extracted_glossary([])

    def _on_summary_or_domain_edited(self) -> None:
        self._schedule_commit()
        self._reset_extraction_worker()
        self._schedule_auto_glossary()

    def _on_auto_glossary_toggled(self, checked: bool) -> None:
        self._update_auto_glossary_button_text(extracting=False)
        if not checked:
            self.auto_glossary_timer.stop()
            self._reset_extraction_worker()
            return
        self._schedule_auto_glossary()

    def _extract_glossary_from_summary(self) -> None:
        if not self.btn_auto_glossary.isChecked():
            return
        summary = self.context_edit.toPlainText().strip()
        if not summary:
            return

        video_language = (
            self._language_getter() if self._language_getter else "Auto Detect"
        ) or "Auto Detect"
        domain = self.domain_edit.text().strip() or "general"
        request_key = (summary, video_language, domain)
        if request_key == self._last_extracted_key:
            return

        self._reset_extraction_worker()
        self._update_auto_glossary_button_text(extracting=True)
        self.diagnostics_label.setText(f"Extracting glossary ({video_language})...")

        worker = _GlossaryExtractionWorker(
            provider_factory=self._llm_provider_factory,
            summary=summary,
            video_language=video_language,
            domain=domain,
            parent=None,
        )
        worker._request_key = request_key
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
        if self._extraction_worker is None or not self.btn_auto_glossary.isChecked():
            return
        self._last_extracted_key = getattr(self._extraction_worker, "_request_key", None)
        self._reset_extraction_worker()
        self._apply_extracted_glossary(extracted_terms)

    def _apply_extracted_glossary(self, extracted_terms: list[str]) -> None:
        if not extracted_terms and not self._auto_managed_terms:
            self.diagnostics_label.setText(
                self._last_diagnostics_text or "No glossary terms found in summary"
            )
            return

        raw_existing = [
            line.strip()
            for line in self.glossary_edit.toPlainText().splitlines()
            if line.strip()
        ]
        existing_all = TranscriptionContext(glossary=raw_existing).normalized().glossary
        # Keep all manually entered terms, dropping only stale auto-managed terms
        manual_existing = [
            term
            for term in existing_all
            if term.casefold() not in self._auto_managed_terms
        ]
        manual_keys = {term.casefold() for term in manual_existing}

        merged = TranscriptionContext(
            context=self.context_edit.toPlainText(),
            glossary=manual_existing + list(extracted_terms),
            domain=self.domain_edit.text().strip() or "general",
        ).normalized()

        self._auto_managed_terms = {
            term.casefold()
            for term in merged.glossary
            if term.casefold() not in manual_keys
        }
        if extracted_terms:
            existing_all_keys = {term.casefold() for term in existing_all}
            added_count = sum(
                1 for term in merged.glossary if term.casefold() not in existing_all_keys
            )
            self.diagnostics_label.setText(
                f"✓ Extracted {len(extracted_terms)} glossary term(s) ({added_count} new)"
            )
        else:
            self.diagnostics_label.setText(
                self._last_diagnostics_text or "No glossary terms found in summary"
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
        self.auto_glossary_timer.stop()
        self._last_extracted_key = None
        self._last_diagnostics_text = None
        self._auto_managed_terms.clear()
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
        self._last_diagnostics_text = text
        self.diagnostics_label.setText(text)
