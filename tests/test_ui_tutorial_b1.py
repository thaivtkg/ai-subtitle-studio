import sys
import weakref
import gc
import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout, QWidget

from core.tutorial.models import AnchorStatus, SurfaceSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.navigation_adapter import AppRouter, NavigationAdapter


class MockAppRouter(AppRouter):
    def __init__(self):
        super().__init__()
        self._index = 0
        self._subroute = None

    def current_index(self):
        return self._index

    def current_subroute(self):
        return self._subroute

    def navigate_to_index(self, index: int, subroute: str = None):
        self._index = index
        self._subroute = subroute
        # Tests deliver transition completion explicitly, without timer races.


class TestMilestoneB1AnchorAndNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.registry = AnchorRegistry()
        self.router = MockAppRouter()
        self.nav = NavigationAdapter(self.router)
        self.widgets = []

    def tearDown(self):
        self.nav.cancel_pending()
        self.registry.clear()
        for widget in self.widgets:
            if widget and shiboken6.isValid(widget):
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_tc139_static_anchor_resolution(self):
        main_window = QWidget()
        main_window.setObjectName("main_window")
        main_window.resize(800, 600)
        button = QPushButton("Test", main_window)
        button.setObjectName("target_btn")
        button.resize(100, 30)
        self.widgets.append(main_window)
        main_window.show()

        self.registry.register("anchor_tc139", button)
        result = self.registry.resolve("anchor_tc139")

        self.assertEqual(result.status, AnchorStatus.RESOLVED)
        self.assertEqual(result.handle.anchor_id, "anchor_tc139")
        self.assertEqual(result.handle.host_id, "main_window")
        self.assertIs(self.registry.get_widget(result.handle), button)

    def test_tc140_dynamic_dialog_anchor(self):
        dialog = QDialog()
        dialog.setObjectName("settings_dialog")
        layout = QVBoxLayout(dialog)
        button = QPushButton("Save")
        button.setObjectName("save_btn")
        layout.addWidget(button)
        self.widgets.append(dialog)
        dialog.show()

        self.registry.register_resolver(
            "anchor_tc140", lambda ref=weakref.ref(dialog): (
                ref().findChild(QPushButton, "save_btn") if ref() is not None else None
            )
        )
        result = self.registry.resolve("anchor_tc140")

        self.assertEqual(result.status, AnchorStatus.RESOLVED)
        self.assertEqual(result.handle.host_id, "settings_dialog")

    def test_tc141_deleted_cpp_object_safe(self):
        window = QWidget()
        button = QPushButton("Delete", window)
        self.widgets.append(window)
        window.show()
        self.registry.register("anchor_tc141", button)

        button.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(button))

        self.assertEqual(
            self.registry.resolve("anchor_tc141").status, AnchorStatus.INVALID
        )

    def test_tc142_hidden_zombie_dialog(self):
        window = QDialog()
        window.resize(800, 600)
        button = QPushButton("Hidden", window)
        button.resize(100, 30)
        self.widgets.append(window)
        window.show()
        window.accept()
        self.registry.register("anchor_tc142", button)

        self.assertEqual(
            self.registry.resolve("anchor_tc142").status, AnchorStatus.NOT_VISIBLE
        )

    def test_tc143_same_surface_queued_ready(self):
        emitted = []
        self.nav.surface_ready.connect(lambda *args: emitted.append(args))

        self.nav.navigate(
            SurfaceSpec("dashboard"), session_id="s1", generation=1, request_id="r1"
        )
        self.assertEqual(emitted, [])

        loop = QEventLoop()
        QTimer.singleShot(5, loop.quit)
        loop.exec()

        self.assertEqual(emitted, [("s1", 1, "r1")])

    def test_tc144_changed_surface_waits_transition(self):
        emitted = []
        self.nav.surface_ready.connect(lambda *args: emitted.append(args))

        self.nav.navigate(
            SurfaceSpec("workspace", "generate"),
            session_id="s2",
            generation=1,
            request_id="r2",
        )
        self.assertEqual(emitted, [])

        loop = QEventLoop()
        QTimer.singleShot(0, lambda: self.router.transition_finished.emit(1))
        QTimer.singleShot(20, loop.quit)
        loop.exec()

        self.assertEqual(emitted, [("s2", 1, "r2")])
        self.assertEqual(self.nav.current_surface(), SurfaceSpec("workspace", "generate"))

    def test_register_does_not_own_widget(self):
        widget = QWidget()
        ref = weakref.ref(widget)
        self.registry.register("weak", widget)
        del widget
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(self.registry.resolve("weak").status, AnchorStatus.NOT_FOUND)

    def test_unregister_and_clear_invalidate_handles(self):
        widget = QWidget()
        self.widgets.append(widget)
        widget.show()
        for clear in (False, True):
            self.registry.register("anchor", widget)
            handle = self.registry.resolve("anchor").handle
            self.assertIsNotNone(handle)
            if clear:
                self.registry.clear()
            else:
                self.registry.unregister("anchor")
            self.assertIsNone(self.registry.get_widget(handle))
            self.assertEqual(self.registry.resolve("anchor").status, AnchorStatus.NOT_FOUND)

    def test_stale_navigation_transition_guarded(self):
        emitted = []
        self.nav.surface_ready.connect(lambda *args: emitted.append(args))
        self.nav.surface_failed.connect(lambda *args: emitted.append(args))
        self.nav.navigate(SurfaceSpec("workspace"), session_id="A", generation=1, request_id="A")
        self.nav.navigate(SurfaceSpec("settings"), session_id="B", generation=1, request_id="B")
        self.router.transition_finished.emit(1)
        self.assertEqual(emitted, [])
        self.router.transition_finished.emit(5)
        self.assertEqual(emitted, [("B", 1, "B")])

    def test_cancel_queued_ready_and_failure(self):
        emitted = []
        self.nav.surface_ready.connect(lambda *args: emitted.append(args))
        self.nav.surface_failed.connect(lambda *args: emitted.append(args))
        for route in ("dashboard", "missing"):
            self.nav.navigate(SurfaceSpec(route), session_id="s", generation=1, request_id="r")
            self.assertEqual(emitted, [])
            self.nav.cancel_pending()
            self.app.processEvents()
            self.assertEqual(emitted, [])

    def test_unknown_route_queued_failure(self):
        emitted = []
        self.nav.surface_failed.connect(lambda *args: emitted.append(args))
        self.nav.navigate(SurfaceSpec("missing"), session_id="s", generation=1, request_id="r")
        self.assertEqual(emitted, [])
        self.app.processEvents()
        self.assertEqual(emitted, [("s", 1, "r", "Unknown route")])
