import gc
import sys
import unittest

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from core.tutorial.models import InteractionKind, InteractionSpec
from ui.tutorial.anchor_registry import AnchorRegistry
from ui.tutorial.dialog_observer import DialogLifecycleObserver
from ui.tutorial.interaction_observer import InteractionObserverAdapter


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
        self.app.processEvents()

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
