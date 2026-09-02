import threading

from PySide6.QtCore import QThread, Signal

from core.media_import.media_import_errors import MediaImportError, MediaImportErrorCode
from core.media_import.media_import_models import MediaImportProgress, MediaImportResult


class MediaImportWorker(QThread):
    progress_changed = Signal(MediaImportProgress)
    succeeded = Signal(MediaImportResult)
    failed = Signal(MediaImportError)
    cancelled = Signal()

    def __init__(self, service, url: str, parent=None, destination_dir=None):
        super().__init__(parent)
        self.service = service
        self.url = url
        self.destination_dir = destination_dir
        self.cancel_flag = threading.Event()

    def run(self):
        try:
            kwargs = {
                "url": self.url,
                "progress_callback": self.progress_changed.emit,
                "cancel_flag": self.cancel_flag,
            }
            if self.destination_dir is not None:
                kwargs["destination_dir"] = self.destination_dir
            result = self.service.import_from_url(**kwargs)
            self.succeeded.emit(result)
        except MediaImportError as exc:
            if exc.code == MediaImportErrorCode.DOWNLOAD_CANCELLED:
                self.cancelled.emit()
            else:
                self.failed.emit(exc)
        except Exception as exc:
            self.failed.emit(
                MediaImportError(
                    MediaImportErrorCode.UNKNOWN,
                    "An unexpected error occurred in the background thread",
                    details={"exception_type": type(exc).__name__},
                )
            )

    def cancel(self):
        self.cancel_flag.set()
