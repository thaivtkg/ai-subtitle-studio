import gc
import sys
import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QTimer, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

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
from ui.tutorial.dialog_observer import DialogLifecycleObserver
from ui.tutorial.interaction_observer import InteractionObserverAdapter


class FakeCatalog:
    def __init__(self, guide):
        self.guide = guide

    def get_guide(self, guide_id):
        return self.guide if self.guide.guide_id == guide_id else None


class FakeNavigation:
    def navigate(self, surface, *, session_id, generation, request_id):
        return None

    def cancel_pending(self):
        return None


class FakeSpotlight:
    def show_target(self, handle, callout, controls):
        return None

    def show_recovery(self, message, retry_enabled, skip_enabled):
        return None

    def hide_step(self):
        return None

    def detach_host(self):
        return None


class FakeDialogObserver:
    def start(self, session_id):
        return None

    def stop(self):
        return None

    def active_modal_handle(self):
        return None


def make_action_step(step_id, anchor, interaction):
    return TourStep(
        step_id=step_id,
        step_type=TourStepType.ACTION,
        callout=CalloutSpec("Title", "Body"),
        safety=SafetySpec(allow_back=False),
        anchor=anchor,
        target_policy=TargetPolicy.REQUIRED,
        interaction=interaction,
    )


class TestMilestoneB3DialogLifecycleObserver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.dialog_observer = DialogLifecycleObserver()
        self.registry = AnchorRegistry()
        self.interaction_observer = InteractionObserverAdapter(
            self.registry, dialog_observer=self.dialog_observer
        )
        self.widgets = []

    def tearDown(self):
        self.interaction_observer.unbind()
        self.dialog_observer.stop()
        for widget in self.widgets:
            if shiboken6.isValid(widget):
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()

    def test_tc158_show_event_tracks_dialog_without_polling(self):
        self.dialog_observer.start("s158")
        dialog = QDialog()
        self.widgets.append(dialog)
        opened = []
        self.dialog_observer.dialog_shown.connect(opened.append)

        dialog.show()
        self.app.processEvents()

        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].startswith("dlg-"))
        self.assertIs(self.dialog_observer.active_dialog(), dialog)
        self.assertEqual(self.dialog_observer.active_modal_handle(), opened[0])

    def test_tc158_tour_advances_inside_real_dialog_exec(self):
        self.dialog_observer.start("s158-e2e")
        open_button = QPushButton("Open")
        self.widgets.append(open_button)
        open_button.show()
        dialog = QDialog()
        confirm_button = QPushButton("Confirm", dialog)
        confirm_button.setObjectName("confirm")
        self.widgets.append(dialog)
        open_button.clicked.connect(dialog.exec)
        confirm_button.clicked.connect(dialog.accept)

        self.registry.register("open", open_button)
        self.registry.register_resolver(
            "confirm",
            lambda: (
                self.dialog_observer.active_dialog().findChild(QPushButton, "confirm")
                if self.dialog_observer.active_dialog()
                else None
            ),
        )
        guide = TourDefinition(
            schema_version=1,
            guide_id="g158-e2e",
            content_version=1,
            title="E2E",
            category="test",
            estimated_minutes=1,
            steps=(
                make_action_step("open", "open", InteractionSpec(InteractionKind.CLICK)),
                make_action_step("confirm", "confirm", InteractionSpec(InteractionKind.CLICK)),
            ),
        )
        engine = TourEngine(
            catalog=FakeCatalog(guide),
            anchor_registry=self.registry,
            navigation=FakeNavigation(),
            interaction_observer=self.interaction_observer,
            spotlight=FakeSpotlight(),
            dialog_observer=self.dialog_observer,
            progress_store=None,
            environment=TourEnvironment(lambda _: True),
        )
        engine.start("g158-e2e")

        def click_confirm_inside_modal():
            self.assertEqual(engine.current_step().step_id, "confirm")
            self.assertEqual(engine.state(), TourState.WAITING_ACTION)
            event_args = (
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease
            )
            for event_type in event_args:
                self.app.sendEvent(
                    confirm_button,
                    QMouseEvent(
                        event_type,
                        QPointF(2, 2), QPointF(2, 2),
                        Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier,
                    ),
                )

        QTimer.singleShot(20, click_confirm_inside_modal)
        self.app.processEvents()
        for event_type in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            self.app.sendEvent(
                open_button,
                QMouseEvent(
                    event_type,
                    QPointF(2, 2), QPointF(2, 2),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                ),
            )
        self.assertEqual(engine.state(), TourState.COMPLETED)

    def test_tc159_reject_removes_dialog_immediately(self):
        self.dialog_observer.start("s159")
        dialog = QDialog()
        self.widgets.append(dialog)
        dialog.show()
        self.app.processEvents()
        handle = self.dialog_observer.active_modal_handle()
        closed = []
        rejected = []
        self.dialog_observer.dialog_finished.connect(lambda d_id, r: closed.append((d_id, r)))
        self.dialog_observer.dialog_rejected.connect(rejected.append)

        dialog.reject()

        self.assertFalse(self.dialog_observer.has_active_dialog())
        self.assertEqual(rejected, [handle])
        self.assertEqual(closed, [(handle, QDialog.DialogCode.Rejected)])

    def test_dialog_handle_stays_unique_and_destroyed_is_not_duplicated_on_reshow(self):
        self.dialog_observer.start("s-reshow")
        dialog = QDialog()
        self.widgets.append(dialog)
        destroyed = []
        self.dialog_observer.dialog_destroyed.connect(destroyed.append)

        dialog.show()
        self.app.processEvents()
        handle = self.dialog_observer.active_modal_handle()
        dialog.reject()
        self.assertIsNone(self.dialog_observer.dialog_for_handle(handle))

        dialog.show()
        self.app.processEvents()
        self.assertEqual(self.dialog_observer.active_modal_handle(), handle)
        dialog.reject()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        self.assertEqual(destroyed, [handle])

    def test_tc160_dialog_accepted_satisfies_interaction(self):
        dialog = QDialog()
        self.widgets.append(dialog)
        dialog.show()
        self.app.processEvents()
        self.registry.register("dialog", dialog)
        handle = self.registry.resolve("dialog").handle
        emitted = []
        self.interaction_observer.action_satisfied.connect(lambda *args: emitted.append(args))

        self.interaction_observer.bind(
            handle,
            InteractionSpec(InteractionKind.DIALOG_ACCEPTED),
            session_id="s160",
            generation=1,
        )
        dialog.accept()

        self.assertEqual(emitted, [("s160", 1)])

    def test_tc160_reject_emits_target_lost(self):
        dialog = QDialog()
        self.widgets.append(dialog)
        dialog.show()
        self.app.processEvents()
        self.registry.register("reject_dialog", dialog)
        handle = self.registry.resolve("reject_dialog").handle
        lost = []
        self.interaction_observer.target_lost.connect(lambda *args: lost.append(args))

        self.interaction_observer.bind(
            handle,
            InteractionSpec(InteractionKind.DIALOG_ACCEPTED),
            session_id="s160-reject",
            generation=2,
        )
        dialog.reject()

        self.assertFalse(self.interaction_observer.is_bound())
        self.assertEqual(lost[0][:2], ("s160-reject", 2))
        self.assertIn("DIALOG_CLOSED_WITHOUT_ACCEPT", lost[0][2])

    def test_tc161_real_escape_rejects_modal_and_recovers(self):
        dialog = QDialog()
        self.widgets.append(dialog)
        dialog.show()
        self.app.processEvents()
        self.registry.register("esc_dialog", dialog)
        handle = self.registry.resolve("esc_dialog").handle
        guide = TourDefinition(
            schema_version=1,
            guide_id="g161-esc",
            content_version=1,
            title="Escape",
            category="test",
            estimated_minutes=1,
            steps=(make_action_step(
                "esc", "esc_dialog", InteractionSpec(InteractionKind.DIALOG_ACCEPTED)
            ),),
        )
        engine = TourEngine(
            catalog=FakeCatalog(guide),
            anchor_registry=self.registry,
            navigation=FakeNavigation(),
            interaction_observer=self.interaction_observer,
            spotlight=FakeSpotlight(),
            dialog_observer=self.dialog_observer,
            progress_store=None,
            environment=TourEnvironment(lambda _: True),
        )
        engine.start("g161-esc")
        self.assertEqual(engine.state(), TourState.WAITING_ACTION)

        QTimer.singleShot(
            0,
            lambda: self.app.sendEvent(
                dialog,
                QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
            ),
        )
        self.assertEqual(dialog.exec(), QDialog.DialogCode.Rejected)
        self.assertEqual(engine.state(), TourState.RECOVERING)

    def test_tc161_nested_dialogs_unwind_lifo_and_destroy_safely(self):
        self.dialog_observer.start("s161")
        parent = QDialog()
        child = QDialog(parent)
        self.widgets.extend([parent, child])
        parent.show()
        self.app.processEvents()
        child.show()
        self.app.processEvents()
        self.assertIs(self.dialog_observer.active_dialog(), child)

        child.accept()
        self.assertIs(self.dialog_observer.active_dialog(), parent)
        parent.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        self.assertIsNone(self.dialog_observer.active_dialog())

    def test_real_qdialog_exec_closes_and_untracks(self):
        self.dialog_observer.start("s-exec")
        dialog = QDialog()
        self.widgets.append(dialog)
        QTimer.singleShot(0, dialog.accept)

        self.assertEqual(dialog.exec(), QDialog.DialogCode.Accepted)
        self.assertFalse(self.dialog_observer.has_active_dialog())
