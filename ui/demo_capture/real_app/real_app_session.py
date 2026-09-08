import os
import shutil
import tempfile
from contextlib import contextmanager

from PySide6.QtWidgets import QApplication

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.runtime.runtime_paths import RuntimePaths


@contextmanager
def capture_owned_real_app_session():
    app = QApplication.instance() or QApplication([])
    previous_localappdata = os.environ.get("LOCALAPPDATA")
    temp_dir = tempfile.mkdtemp(prefix="ai_subtitle_real_capture_")
    os.environ["LOCALAPPDATA"] = temp_dir
    pre_existing_widgets = set(app.topLevelWidgets())
    cleanup_errors = []

    try:
        RuntimePaths.ensure_user_data_dirs()
        yield temp_dir
    finally:
        try:
            for widget in set(app.topLevelWidgets()) - pre_existing_widgets:
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
