from enum import Enum, auto

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportProgress, MediaImportResult, MediaImportStage
from workers.media_import_worker import MediaImportWorker


STAGE_TRANSLATIONS = {
    MediaImportStage.RESOLVING: "Resolving media...",
    MediaImportStage.DOWNLOADING: "Downloading media...",
    MediaImportStage.VALIDATING: "Validating media...",
    MediaImportStage.FINALIZING: "Finalizing import...",
}


class MediaImportDialogState(Enum):
    IDLE = auto()
    RESOLVING = auto()
    DOWNLOADING = auto()
    VALIDATING = auto()
    FINALIZING = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    CANCELLING = auto()
    CANCELLED = auto()


def translate_error(error: MediaImportError) -> str:
    messages = {
        MediaImportErrorCode.AUTH_REQUIRED: "This media requires login. Please use a public URL.",
        MediaImportErrorCode.UNSUPPORTED_URL: "The URL is not supported or does not contain extractable media.",
        MediaImportErrorCode.NO_VIDEO_STREAM: "The media file does not contain a valid video stream.",
        MediaImportErrorCode.INVALID_URL: "The provided URL is invalid or malformed.",
        MediaImportErrorCode.UNSAFE_URL: "The URL is blocked by security policies.",
        MediaImportErrorCode.DRM_OR_PROTECTED: "This media is DRM protected and cannot be downloaded.",
        MediaImportErrorCode.TIMEOUT: "The connection timed out. Please check your network and try again.",
        MediaImportErrorCode.NETWORK_ERROR: "A network error occurred. Please check your connection.",
        MediaImportErrorCode.DISK_FULL: "Not enough disk space to save the media.",
        MediaImportErrorCode.PERMISSION_DENIED: "Permission denied while saving the media.",
        MediaImportErrorCode.MEDIA_NOT_FOUND: "The downloaded media could not be found.",
        MediaImportErrorCode.INVALID_MEDIA: "The media file is corrupt, empty, or invalid.",
        MediaImportErrorCode.FINALIZE_FAILED: "Failed to finalize the imported media.",
        MediaImportErrorCode.DOWNLOAD_CANCELLED: "Import cancelled by user.",
        MediaImportErrorCode.HTTP_ERROR: "An HTTP error occurred while downloading.",
    }
    return messages.get(error.code, f"An error occurred: {error}")


class MediaImportDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.worker = None
        self.result = None
        self.current_state = MediaImportDialogState.IDLE
        self._close_pending = False
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Import Media")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        layout = QVBoxLayout(self)
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import_clicked)
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        buttons.addWidget(self.import_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        self._set_state(MediaImportDialogState.IDLE)

    def _set_state(self, state: MediaImportDialogState):
        order = {
            MediaImportDialogState.RESOLVING: 1,
            MediaImportDialogState.DOWNLOADING: 2,
            MediaImportDialogState.VALIDATING: 3,
            MediaImportDialogState.FINALIZING: 4,
        }
        if self.current_state in (MediaImportDialogState.CANCELLING, MediaImportDialogState.CANCELLED):
            if state not in (MediaImportDialogState.CANCELLED, MediaImportDialogState.IDLE, MediaImportDialogState.FAILED):
                return
        if state in order and self.current_state in order and order[state] < order[self.current_state]:
            return
        self.current_state = state
        if state == MediaImportDialogState.IDLE:
            self.url_input.setEnabled(True)
            self.import_btn.setEnabled(True)
            self.cancel_btn.setText("Close")
            self.cancel_btn.setEnabled(True)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.status_label.setText("Ready")
        elif state in order:
            self.url_input.setEnabled(False)
            self.import_btn.setEnabled(False)
            self.cancel_btn.setText("Cancel")
            self.cancel_btn.setEnabled(True)
        elif state == MediaImportDialogState.CANCELLING:
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
        elif state == MediaImportDialogState.CANCELLED:
            self.status_label.setText("Import cancelled.")
        elif state == MediaImportDialogState.SUCCEEDED:
            pass
        elif state == MediaImportDialogState.FAILED:
            self.status_label.setText("Import failed.")

    def _on_import_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self._set_state(MediaImportDialogState.RESOLVING)
        self.worker = MediaImportWorker(self.service, url)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.succeeded.connect(self._on_succeeded)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.finished.connect(self._on_worker_thread_finished)
        self.worker.start()

    def _on_cancel_clicked(self):
        if self.current_state in {
            MediaImportDialogState.RESOLVING,
            MediaImportDialogState.DOWNLOADING,
            MediaImportDialogState.VALIDATING,
            MediaImportDialogState.FINALIZING,
        }:
            self._set_state(MediaImportDialogState.CANCELLING)
            self.worker.cancel()
        else:
            self.reject()

    def _on_progress(self, progress: MediaImportProgress):
        if self.current_state in {
            MediaImportDialogState.CANCELLING,
            MediaImportDialogState.CANCELLED,
            MediaImportDialogState.FAILED,
            MediaImportDialogState.SUCCEEDED,
        }:
            return
        state = {
            MediaImportStage.RESOLVING: MediaImportDialogState.RESOLVING,
            MediaImportStage.DOWNLOADING: MediaImportDialogState.DOWNLOADING,
            MediaImportStage.VALIDATING: MediaImportDialogState.VALIDATING,
            MediaImportStage.FINALIZING: MediaImportDialogState.FINALIZING,
        }[progress.stage]
        self._set_state(state)
        text = STAGE_TRANSLATIONS[progress.stage]
        if progress.stage == MediaImportStage.DOWNLOADING and progress.percent is not None:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(progress.percent))
        else:
            self.progress_bar.setRange(0, 0)
        self.status_label.setText(text)

    def _on_succeeded(self, result: MediaImportResult):
        self.result = result
        self._set_state(MediaImportDialogState.SUCCEEDED)

    def _on_failed(self, error: MediaImportError):
        if not self._close_pending:
            QMessageBox.critical(self, "Import Failed", translate_error(error))
        self._set_state(MediaImportDialogState.FAILED)

    def _on_cancelled(self):
        self._set_state(MediaImportDialogState.CANCELLED)

    def _on_worker_thread_finished(self):
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self._close_pending:
            self.reject()
        elif self.current_state == MediaImportDialogState.SUCCEEDED:
            self.accept()
        else:
            self._set_state(MediaImportDialogState.IDLE)

    def closeEvent(self, event):
        if self.current_state in {
            MediaImportDialogState.RESOLVING,
            MediaImportDialogState.DOWNLOADING,
            MediaImportDialogState.VALIDATING,
            MediaImportDialogState.FINALIZING,
        }:
            event.ignore()
            self._close_pending = True
            self._set_state(MediaImportDialogState.CANCELLING)
            self.worker.cancel()
        elif self.current_state == MediaImportDialogState.CANCELLING:
            event.ignore()
            self._close_pending = True
        else:
            event.accept()

    def get_result(self) -> MediaImportResult | None:
        return self.result
