import os
import shutil
import tempfile
import time
from contextlib import contextmanager

from PySide6.QtWidgets import QApplication

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import CaptureScenario, ExecutionMode
from core.runtime.runtime_paths import RuntimePaths
from ui.Gui import MainWindow
from ui.demo_capture.action_driver import UIActionDriver
from ui.demo_capture.anchor_registry_adapter import AnchorRegistryCaptureAdapter
from ui.demo_capture.navigation_adapter import CaptureNavigationAdapter


@contextmanager
def isolated_app_environment(scenario: CaptureScenario, mode: ExecutionMode):
    if mode != ExecutionMode.ISOLATED:
        raise CaptureRunError(
            CaptureErrorCode.REAL_APP_ENVIRONMENT_UNAVAILABLE,
            "isolated_app_environment only supports ISOLATED mode",
        )

    app = QApplication.instance() or QApplication([])
    previous_localappdata = os.environ.get("LOCALAPPDATA")
    temp_dir = tempfile.mkdtemp(prefix="ai_subtitle_demo_capture_")
    os.environ["LOCALAPPDATA"] = temp_dir
    main_window = None

    try:
        RuntimePaths.ensure_user_data_dirs()
        main_window = MainWindow(None)
        main_window.resize(*scenario.profile.window_size)
        main_window.show()
        app.processEvents()

        registry = main_window.tour_anchor_registry
        resolver = AnchorRegistryCaptureAdapter(registry)
        navigation = CaptureNavigationAdapter(main_window)

        def event_pump() -> None:
            app.processEvents()

        action_driver = UIActionDriver(
            resolver=resolver,
            navigation=navigation,
            event_pump=event_pump,
            clock=time.monotonic,
            capture_root=main_window,
        )
        yield main_window, action_driver, resolver
    finally:
        try:
            if main_window is not None:
                main_window.close()
                main_window.deleteLater()
                app.processEvents()
        finally:
            if previous_localappdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_localappdata
            shutil.rmtree(temp_dir)


class IsolatedAppFactory:
    def __call__(self, scenario: CaptureScenario, mode: ExecutionMode):
        return isolated_app_environment(scenario, mode)
