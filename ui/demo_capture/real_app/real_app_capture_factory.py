import time
from contextlib import contextmanager

from PySide6.QtWidgets import QApplication

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import CaptureScenario, ExecutionMode
from ui.Gui import MainWindow
from ui.demo_capture.action_driver import UIActionDriver
from ui.demo_capture.anchor_registry_adapter import AnchorRegistryCaptureAdapter
from ui.demo_capture.navigation_adapter import CaptureNavigationAdapter
from ui.demo_capture.real_app.real_app_session import capture_owned_real_app_session


@contextmanager
def real_app_environment(scenario: CaptureScenario, mode: ExecutionMode):
    if mode != ExecutionMode.REAL_APP:
        raise CaptureRunError(
            CaptureErrorCode.INVALID_SCENARIO,
            "real_app_environment only supports REAL_APP mode",
        )

    with capture_owned_real_app_session():
        app = QApplication.instance()
        main_window = MainWindow(None)
        main_window.setFixedSize(*scenario.profile.window_size)
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


class RealAppCaptureFactory:
    def __call__(self, scenario: CaptureScenario, mode: ExecutionMode):
        return real_app_environment(scenario, mode)
