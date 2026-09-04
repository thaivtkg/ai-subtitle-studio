import sys
import unittest

import shiboken6
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QVBoxLayout, QWidget

from core.tutorial.models import AnchorStatus, SurfaceSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.navigation_adapter import AppRouter, NavigationAdapter


class MockAppRouter(AppRouter):
    def __init__(self):
        super().__init__()
        self._route = "dashboard"
        self._subroute = None

    def current_route(self):
        return self._route

    def current_subroute(self):
        return self._subroute

    def navigate_to(self, route: str, subroute: str = None):
        self._route = route
        self._subroute = subroute
        QTimer.singleShot(10, self.transition_finished.emit)


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
        for widget in self.widgets:
            if widget and shiboken6.isValid(widget):
                widget.deleteLater()
        self.app.processEvents()

    def test_tc139_static_anchor_resolution(self):
        main_window = QWidget()
        main_window.setObjectName("main_window")
        main_window.resize(800, 600)
        button = QPushButton("Test", main_window)
        button.setObjectName("target_btn")
        button.resize(100, 30)
        self.widgets.append(main_window)
        main_window.show()

        self.registry.register_resolver(
            "anchor_tc139", lambda: main_window.findChild(QPushButton, "target_btn")
        )
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
            "anchor_tc140", lambda: dialog.findChild(QPushButton, "save_btn")
        )
        result = self.registry.resolve("anchor_tc140")

        self.assertEqual(result.status, AnchorStatus.RESOLVED)
        self.assertEqual(result.handle.host_id, "settings_dialog")

    def test_tc141_deleted_cpp_object_safe(self):
        window = QWidget()
        button = QPushButton("Delete", window)
        self.widgets.append(window)
        window.show()
        self.registry.register_resolver("anchor_tc141", lambda: button)

        button.deleteLater()
        self.app.processEvents()

        self.assertEqual(
            self.registry.resolve("anchor_tc141").status, AnchorStatus.NOT_FOUND
        )

    def test_tc142_hidden_zombie_dialog(self):
        window = QWidget()
        window.resize(800, 600)
        button = QPushButton("Hidden", window)
        button.resize(100, 30)
        self.widgets.append(window)
        window.show()
        window.hide()
        self.registry.register_resolver("anchor_tc142", lambda: button)

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
        QTimer.singleShot(20, loop.quit)
        loop.exec()

        self.assertEqual(emitted, [("s2", 1, "r2")])
        self.assertEqual(self.nav.current_surface(), SurfaceSpec("workspace", "generate"))
