import gc
import sys
import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from core.tutorial.models import InteractionKind, InteractionSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.interaction_observer import InteractionObserverAdapter


class TestMilestoneB2InteractionObserver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.registry = AnchorRegistry()
        self.observer = InteractionObserverAdapter(self.registry)
        self.widgets = []

    def tearDown(self):
        self.observer.unbind()
        self.registry.clear()
        for widget in self.widgets:
            if shiboken6.isValid(widget):
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()

    def _bind(self, widget, kind, anchor_id="anchor"):
        self.widgets.append(widget)
        widget.show()
        self.registry.register(anchor_id, widget)
        resolution = self.registry.resolve(anchor_id)
        self.assertIsNotNone(resolution.handle)
        self.observer.bind(
            resolution.handle,
            InteractionSpec(kind),
            session_id="session",
            generation=7,
        )

    def test_tc148_click_type_and_hover_emit_action(self):
        button = QPushButton("Click")
        emitted = []
        self.observer.action_satisfied.connect(lambda *args: emitted.append(args))
        self._bind(button, InteractionKind.CLICK)
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.assertFalse(self.observer.eventFilter(button, release))
        self.assertEqual(emitted, [("session", 7)])

        self.observer.unbind()
        line_edit = QLineEdit()
        self._bind(line_edit, "input", "input")
        self.app.sendEvent(
            line_edit,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key_A, Qt.KeyboardModifier.NoModifier, "a"),
        )
        self.assertEqual(len(emitted), 2)

        self.observer.unbind()
        hover = QWidget()
        self._bind(hover, "hover", "hover")
        self.app.sendEvent(hover, QEvent(QEvent.Type.Enter))
        self.assertEqual(len(emitted), 3)

    def test_tc149_event_filter_does_not_swallow_business_click(self):
        button = QPushButton("Business")
        clicked = []
        button.clicked.connect(lambda: clicked.append(True))
        self._bind(button, InteractionKind.CLICK)
        self.app.sendEvent(
            button,
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(5, 5),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        self.app.sendEvent(
            button,
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(5, 5),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        self.assertEqual(clicked, [True])

    def test_tc150_unbind_is_idempotent_and_removes_filter(self):
        button = QPushButton("Unbind")
        emitted = []
        self.observer.action_satisfied.connect(lambda *args: emitted.append(args))
        self._bind(button, InteractionKind.CLICK)
        self.observer.unbind()
        self.observer.unbind()
        self.assertFalse(self.observer.is_bound())
        self.app.sendEvent(button, QEvent(QEvent.Type.Enter))
        self.assertEqual(emitted, [])

    def test_tc151_deleted_cpp_target_emits_target_lost(self):
        window = QWidget()
        button = QPushButton("Delete", window)
        self.widgets.append(window)
        window.show()
        self.registry.register("deleted", button)
        resolution = self.registry.resolve("deleted")
        lost = []
        self.observer.target_lost.connect(lambda *args: lost.append(args))
        self.observer.bind(
            resolution.handle,
            InteractionSpec(InteractionKind.CLICK),
            session_id="session",
            generation=9,
        )
        button.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(button))
        self.assertFalse(self.observer.is_bound())
        self.assertEqual(lost, [("session", 9, "Target widget destroyed by application")])
