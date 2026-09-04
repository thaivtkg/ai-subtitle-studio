import gc
import sys
import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTextEdit, QWidget

from core.tutorial.environment import TourEnvironment
from core.tutorial.models import (
    CalloutSpec,
    InteractionKind,
    InteractionSpec,
    SafetySpec,
    TargetPolicy,
    TourDefinition,
    TourState,
    TourStep,
    TourStepType,
)
from core.tutorial.tour_engine import TourEngine
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.interaction_observer import InteractionObserverAdapter


class TrackingObserver(InteractionObserverAdapter):
    def __init__(self, registry):
        super().__init__(registry)
        self.call_count = 0

    def eventFilter(self, obj, event):
        self.call_count += 1
        return super().eventFilter(obj, event)


class FakeCatalog:
    def __init__(self, guide):
        self.guide = guide

    def get_guide(self, guide_id):
        return self.guide if self.guide.guide_id == guide_id else None


class FakeNavigation:
    def navigate(self, *args, **kwargs):
        pass

    def cancel_pending(self):
        pass


class FakeSpotlight:
    def show_target(self, *args, **kwargs):
        return True

    def show_recovery(self, *args, **kwargs):
        pass

    def hide_step(self):
        pass

    def detach_host(self):
        pass


class FakeDialogObserver:
    def start(self, session_id):
        pass

    def stop(self):
        pass


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

    def test_tc148_enum_interactions_emit_action(self):
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
        self._bind(line_edit, InteractionKind.TEXT_COMMITTED, "input")
        line_edit.editingFinished.emit()
        self.assertEqual(len(emitted), 2)

        self.observer.unbind()
        combo = QComboBox()
        combo.addItems(["A", "B"])
        self._bind(combo, InteractionKind.SELECTION_CHANGED, "selection")
        combo.setCurrentIndex(1)
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
        tracking = TrackingObserver(self.registry)
        self.widgets.append(button)
        button.show()
        self.registry.register("tracking", button)
        handle = self.registry.resolve("tracking").handle
        tracking.bind(handle, InteractionSpec(InteractionKind.CLICK), session_id="s", generation=1)
        self.app.sendEvent(button, QEvent(QEvent.Type.Enter))
        count_before = tracking.call_count
        self.assertGreater(count_before, 0)
        tracking.unbind()
        tracking.unbind()
        self.app.sendEvent(button, QEvent(QEvent.Type.Enter))
        self.assertEqual(tracking.call_count, count_before)
        tracking.bind(handle, InteractionSpec(InteractionKind.CLICK), session_id="s2", generation=2)
        self.app.sendEvent(button, QEvent(QEvent.Type.Enter))
        self.assertEqual(tracking.call_count, count_before + 1)

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

    def test_tc151_target_destroyed_during_waiting_action_recovers_engine(self):
        button = QPushButton("Doomed")
        self.widgets.append(button)
        button.show()
        self.registry.register("engine_target", button)
        guide = TourDefinition(
            schema_version=1,
            guide_id="guide",
            content_version=1,
            title="Test",
            category="test",
            estimated_minutes=1,
            steps=(TourStep(
                "action",
                TourStepType.ACTION,
                CalloutSpec("Title", "Body"),
                SafetySpec(False),
                anchor="engine_target",
                target_policy=TargetPolicy.REQUIRED,
                interaction=InteractionSpec(InteractionKind.CLICK),
            ),),
        )
        engine = TourEngine(
            FakeCatalog(guide),
            self.registry,
            FakeNavigation(),
            self.observer,
            FakeSpotlight(),
            FakeDialogObserver(),
            None,
            TourEnvironment(lambda _: True),
        )
        self.assertTrue(engine.start("guide"))
        self.assertEqual(engine.state(), TourState.WAITING_ACTION)
        button.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(self.observer.is_bound())
        self.assertEqual(engine.state(), TourState.RECOVERING)

    def test_dialog_accepted_is_deferred_to_b3(self):
        button = QPushButton("Dialog")
        self.widgets.append(button)
        button.show()
        self.registry.register("dialog", button)
        handle = self.registry.resolve("dialog").handle
        with self.assertRaises(NotImplementedError):
            self.observer.bind(
                handle,
                InteractionSpec(InteractionKind.DIALOG_ACCEPTED),
                session_id="s",
                generation=1,
            )

    def test_text_commit_without_semantic_signal_fails_safe(self):
        text_edit = QTextEdit()
        self.widgets.append(text_edit)
        text_edit.show()
        self.registry.register("text_edit", text_edit)
        handle = self.registry.resolve("text_edit").handle
        lost = []
        self.observer.target_lost.connect(lambda *args: lost.append(args))

        self.observer.bind(
            handle,
            InteractionSpec(InteractionKind.TEXT_COMMITTED),
            session_id="s",
            generation=1,
        )
        self.assertFalse(self.observer.is_bound())
        self.assertIn("INTERACTION_BIND_FAILED", lost[0][2])

    def test_selection_without_semantic_signal_fails_safe(self):
        button = QPushButton("No selection")
        self.widgets.append(button)
        button.show()
        self.registry.register("no_selection", button)
        handle = self.registry.resolve("no_selection").handle
        lost = []
        self.observer.target_lost.connect(lambda *args: lost.append(args))

        self.observer.bind(
            handle,
            InteractionSpec(InteractionKind.SELECTION_CHANGED),
            session_id="s",
            generation=1,
        )
        self.assertFalse(self.observer.is_bound())
        self.assertIn("INTERACTION_BIND_FAILED", lost[0][2])

    def test_non_schema_interaction_alias_is_rejected(self):
        button = QPushButton("Alias")
        self.widgets.append(button)
        button.show()
        self.registry.register("alias", button)
        handle = self.registry.resolve("alias").handle
        with self.assertRaises(ValueError):
            self.observer.bind(
                handle,
                InteractionSpec("hover"),
                session_id="s",
                generation=1,
            )
