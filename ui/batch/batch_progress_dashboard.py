from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QScrollArea, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt
from ui.theme import Theme
from core.batch.batch_models import BatchSession, BatchStatus


class BatchJobRow(QWidget):
    """A single row showing one job's file name, status, and progress."""

    def __init__(self, job_id: str, filename: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.name_label = QLabel(filename)
        self.name_label.setFixedWidth(200)
        self.name_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.name_label)

        self.status_label = QLabel("PENDING")
        self.status_label.setFixedWidth(100)
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER};
                border-radius: 4px; height: 18px; text-align: center; color: {Theme.TEXT_PRIMARY}; font-size: 11px; }}
            QProgressBar::chunk {{ background-color: {Theme.PRIMARY_PURPLE}; border-radius: 3px; }}
        """)
        layout.addWidget(self.progress_bar)

    _STATUS_COLORS = {
        BatchStatus.PENDING: Theme.TEXT_MUTED,
        BatchStatus.EXTRACTING: Theme.CYAN,
        BatchStatus.TRANSLATING: Theme.WARNING,
        BatchStatus.EXPORTING: Theme.PRIMARY_PURPLE,
        BatchStatus.COMPLETED: Theme.SUCCESS,
        BatchStatus.FAILED: Theme.DANGER,
    }

    def update_status(self, status: BatchStatus):
        self.status_label.setText(status.value)
        color = self._STATUS_COLORS.get(status, Theme.TEXT_MUTED)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        if status == BatchStatus.COMPLETED:
            self.progress_bar.setValue(100)

    def update_progress(self, value: int):
        self.progress_bar.setValue(value)


class BatchProgressDashboard(QWidget):
    """Dashboard view showing batch processing progress for all jobs."""

    def __init__(self, session: BatchSession, batch_manager, parent=None):
        super().__init__(parent)
        self.session = session
        self.batch_manager = batch_manager
        self.job_rows = {}
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        self.setStyleSheet(f"background-color: {Theme.BG_APP};")

        # Header
        header = QLabel(f"Batch Processing — {len(self.session.jobs)} files")
        header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(header)

        # Overall progress
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, len(self.session.jobs))
        self.overall_bar.setValue(0)
        self.overall_bar.setFormat("%v / %m completed")
        self.overall_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: {Theme.SURFACE}; border: 1px solid {Theme.BORDER};
                border-radius: 6px; height: 24px; text-align: center; color: {Theme.TEXT_PRIMARY}; font-size: 13px; }}
            QProgressBar::chunk {{ background-color: {Theme.SUCCESS}; border-radius: 5px; }}
        """)
        layout.addWidget(self.overall_bar)

        # Scroll area for job rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {Theme.BG_APP}; }}")

        container = QWidget()
        self.jobs_layout = QVBoxLayout(container)
        self.jobs_layout.setSpacing(2)
        self.jobs_layout.setContentsMargins(0, 0, 0, 0)

        import os
        for job in self.session.jobs:
            row = BatchJobRow(job.id, os.path.basename(job.input_file))
            self.job_rows[job.id] = row
            self.jobs_layout.addWidget(row)

        self.jobs_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Status summary
        self.summary_label = QLabel("Waiting to start...")
        self.summary_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(self.summary_label)

    def _connect_signals(self):
        self.batch_manager.job_status_changed.connect(self._on_status_changed)
        self.batch_manager.job_progress_updated.connect(self._on_progress_updated)
        self.batch_manager.session_completed.connect(self._on_session_completed)

    def _on_status_changed(self, job_id: str, status: BatchStatus):
        row = self.job_rows.get(job_id)
        if row:
            row.update_status(status)
        # Update overall progress
        done = sum(1 for j in self.session.jobs if j.status in (BatchStatus.COMPLETED, BatchStatus.FAILED))
        self.overall_bar.setValue(done)
        self.summary_label.setText(f"Processing: {job_id} — {status.value}")

    def _on_progress_updated(self, job_id: str, progress: int):
        row = self.job_rows.get(job_id)
        if row:
            row.update_progress(progress)

    def _on_session_completed(self):
        completed = sum(1 for j in self.session.jobs if j.status == BatchStatus.COMPLETED)
        failed = sum(1 for j in self.session.jobs if j.status == BatchStatus.FAILED)
        self.summary_label.setText(f"Batch complete: {completed} succeeded, {failed} failed.")
        self.summary_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px; font-weight: 600;")
