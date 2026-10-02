import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from core.recovery.recovery_models import RecoveryEntry


class _DialogFixture:
    def __init__(self, entries=None, confirm=True):
        self.entries = list(entries or [])
        self.confirm = confirm
        self.restore_calls = []
        self.delete_calls = []
        self.refresh_count = 0

    def list_entries(self):
        self.refresh_count += 1
        return list(self.entries)

    def live_session_id(self):
        return "live-session"

    def restore(self, session_id, *, linked, active_session_id):
        self.restore_calls.append((session_id, linked, active_session_id))
        return True

    def delete(self, session_id, *, active_session_id):
        self.delete_calls.append((session_id, active_session_id))
        self.entries = [entry for entry in self.entries if entry.session_id != session_id]
        return True


def _entry(
    session_id="session-a",
    project_root=r"D:\Temp\Test\da.ai-subtitle",
    timestamp="2026-09-21T05:20:00+00:00",
    revision=12,
    source_status="AVAILABLE",
):
    return RecoveryEntry(
        session_id=session_id,
        project_id=f"project-{session_id}",
        project_root=project_root,
        video_path=r"D:\video\shared.mp4",
        effective_snapshot_timestamp=timestamp,
        created_at=timestamp,
        snapshot_revision=revision,
        last_saved_revision=revision - 1,
        last_clean_revision=revision - 1,
        source_status=source_status,
        unlinked_restore_allowed=source_status != "AVAILABLE",
        linked_restore_allowed=source_status == "AVAILABLE",
    )


class RecoveryCenterUiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        try:
            from ui.dialogs.recovery_center_dialog import RecoveryCenterDialog
        except ImportError as error:
            self.fail(f"RecoveryCenterDialog is not implemented yet: {error}")
        self.RecoveryCenterDialog = RecoveryCenterDialog

    def make_dialog(self, fixture):
        return self.RecoveryCenterDialog(
            entries_provider=fixture.list_entries,
            live_session_id_provider=fixture.live_session_id,
            restore_callback=fixture.restore,
            delete_callback=fixture.delete,
            confirm_callback=lambda *_args: fixture.confirm,
        )

    def tearDown(self):
        for dialog in self.__dict__.get("_dialogs", []):
            dialog.close()

    def keep(self, dialog):
        self._dialogs = getattr(self, "_dialogs", [])
        self._dialogs.append(dialog)
        return dialog

    def buttons(self, dialog, text):
        return [button for button in dialog.findChildren(QPushButton) if button.text() == text]

    def test_UI01_empty_state_has_no_entry_actions(self):
        dialog = self.keep(self.make_dialog(_DialogFixture()))

        self.assertIn("Không có dữ liệu khôi phục.", dialog.displayed_text())
        self.assertFalse(self.buttons(dialog, "Restore"))
        self.assertFalse(self.buttons(dialog, "Restore Unlinked"))
        self.assertFalse(self.buttons(dialog, "Delete"))
        self.assertTrue(self.buttons(dialog, "Close"))

    def test_UI02_available_entry_shows_required_fields(self):
        fixture = _DialogFixture([_entry()])
        dialog = self.keep(self.make_dialog(fixture))

        text = dialog.displayed_text()
        self.assertIn("da", text)
        self.assertIn("21/09/2026 05:20", text)
        self.assertIn("Revision 12", text)
        self.assertIn("Source available", text)

    def test_UI03_keeps_domain_order_without_ui_resorting(self):
        fixture = _DialogFixture([
            _entry("session-b", r"D:\B.ai-subtitle"),
            _entry("session-a", r"D:\A.ai-subtitle"),
        ])
        dialog = self.keep(self.make_dialog(fixture))

        text = dialog.displayed_text()
        self.assertLess(text.index("B"), text.index("A"))

    def test_UI04_available_restore_uses_linked_mode_and_session_id(self):
        fixture = _DialogFixture([_entry()])
        dialog = self.keep(self.make_dialog(fixture))

        self.buttons(dialog, "Restore")[0].click()

        self.assertEqual(fixture.restore_calls, [("session-a", True, "live-session")])

    def test_UI05_missing_source_restore_uses_unlinked_mode(self):
        fixture = _DialogFixture([_entry(source_status="SOURCE_MISSING")])
        dialog = self.keep(self.make_dialog(fixture))

        self.assertTrue(self.buttons(dialog, "Restore Unlinked"))
        self.buttons(dialog, "Restore Unlinked")[0].click()

        self.assertEqual(fixture.restore_calls, [("session-a", False, "live-session")])

    def test_UI06_confirmed_delete_uses_session_id_and_refreshes(self):
        fixture = _DialogFixture([_entry()])
        dialog = self.keep(self.make_dialog(fixture))
        before = fixture.refresh_count

        self.buttons(dialog, "Delete")[0].click()

        self.assertEqual(fixture.delete_calls, [("session-a", "live-session")])
        self.assertGreater(fixture.refresh_count, before)
        self.assertNotIn("\nda\n", f"\n{dialog.displayed_text()}\n")

    def test_UI07_cancelled_delete_does_not_call_domain(self):
        fixture = _DialogFixture([_entry()], confirm=False)
        dialog = self.keep(self.make_dialog(fixture))

        self.buttons(dialog, "Delete")[0].click()

        self.assertEqual(fixture.delete_calls, [])

    def test_UI08_stale_action_refreshes_without_targeting_another_row(self):
        fixture = _DialogFixture([_entry()])
        fixture.restore = MagicMock(return_value=False)
        dialog = self.keep(self.make_dialog(fixture))
        before = fixture.refresh_count

        self.buttons(dialog, "Restore")[0].click()

        self.assertGreater(fixture.refresh_count, before)
        fixture.restore.assert_called_once_with(
            "session-a", linked=True, active_session_id="live-session"
        )

    def test_UI09_provider_excludes_explicit_live_session(self):
        live = _entry("live-session")
        persisted = _entry("persisted-session", r"D:\Persisted.ai-subtitle")
        calls = []

        def provider():
            active_session_id = "live-session"
            calls.append(active_session_id)
            return [entry for entry in (live, persisted) if entry.session_id != active_session_id]

        dialog = self.keep(
            self.RecoveryCenterDialog(
                entries_provider=provider,
                live_session_id_provider=lambda: "live-session",
                restore_callback=MagicMock(return_value=True),
                delete_callback=MagicMock(return_value=True),
                confirm_callback=lambda *_args: True,
            )
        )

        self.assertEqual(calls, ["live-session"])
        self.assertNotIn("live-session", dialog.entry_session_ids())
        self.assertEqual(dialog.entry_session_ids(), ["persisted-session"])

    def test_UI10_sidebar_has_recovery_center_action_without_new_route(self):
        from ui.Gui import MainWindow

        with patch.object(MainWindow, "open_recovery_center") as open_center:
            window = MainWindow(
                project_service=MagicMock(),
                media_import_service=MagicMock(),
            )
            try:
                button = window.findChild(QPushButton, "btn_recovery_center")
                self.assertIsNotNone(button)
                self.assertIn("Recovery Center", button.text())
                button.click()
                open_center.assert_called_once_with()
                self.assertNotIn("RecoveryCenter", str(getattr(window, "stack", "")))
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
