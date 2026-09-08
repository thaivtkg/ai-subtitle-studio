import os
import shutil
import tempfile
from contextlib import contextmanager

from PySide6.QtWidgets import QApplication, QWidget

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.runtime.runtime_paths import RuntimePaths


@contextmanager
def capture_owned_real_app_session():
    app = QApplication.instance() or QApplication([])
    previous_localappdata = os.environ.get("LOCALAPPDATA")
    temp_dir = tempfile.mkdtemp(prefix="ai_subtitle_real_capture_")
    os.environ["LOCALAPPDATA"] = temp_dir
    owned_roots = []
    cleanup_errors = []

    def own(widget) -> None:
        if widget not in owned_roots:
            owned_roots.append(widget)

    try:
        RuntimePaths.ensure_user_data_dirs()
        yield own
    finally:
        try:
            for root in owned_roots:
                owned_widgets = [
                    widget
                    for widget in root.findChildren(QWidget)
                    if widget.isWindow()
                ]
                owned_widgets.append(root)
                for widget in reversed(owned_widgets):
                    widget.close()
                    widget.deleteLater()
            app.processEvents()
        except Exception as error:
            cleanup_errors.append(str(error))

        try:
            if previous_localappdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_localappdata
        except Exception as error:
            cleanup_errors.append(str(error))

        try:
            shutil.rmtree(temp_dir)
        except Exception as error:
            cleanup_errors.append(str(error))

        if cleanup_errors:
            raise CaptureRunError(
                CaptureErrorCode.CLEANUP_FAILED,
                f"Real app session cleanup failed: {'; '.join(cleanup_errors)}",
            )
