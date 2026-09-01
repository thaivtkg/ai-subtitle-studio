import os
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

from core.runtime.single_instance_guard import IpcAction, IpcRequest
from main import build_ipc_request, run_secondary_instance
from ui.dialogs.recovery_dialog import RecoveryChoice, RecoveryDialog
from ui.dialogs.source_mismatch_dialog import (
    SourceMismatchChoice,
    SourceMismatchDialog,
)


class TestRecoveryUiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_build_ipc_request_routes_paths(self):
        self.assertEqual(build_ipc_request(["app"]), IpcRequest(IpcAction.ACTIVATE_WINDOW))
        with tempfile.TemporaryDirectory(suffix=".ai-subtitle") as directory:
            self.assertEqual(
                build_ipc_request(["app", directory]),
                IpcRequest(IpcAction.OPEN_PROJECT, os.path.abspath(directory)),
            )
        self.assertEqual(
            build_ipc_request(["app", "movie.mp4"]),
            IpcRequest(IpcAction.OPEN_MEDIA, os.path.abspath("movie.mp4")),
        )

    def test_secondary_path_does_not_construct_main_window(self):
        guard = type("Guard", (), {"relay_to_primary": lambda self, request: True, "close": lambda self: None})()
        with patch("main.Gui") as window:
            self.assertEqual(run_secondary_instance(guard, ["app"]), 0)
            window.assert_not_called()

    def test_recovery_dialog_exposes_only_restore_and_discard(self):
        dialog = RecoveryDialog("session", "project", "timestamp")
        self.assertEqual(dialog.choices, (RecoveryChoice.RESTORE, RecoveryChoice.DISCARD))

    def test_source_mismatch_dialog_exposes_unlinked_restore_and_discard(self):
        dialog = SourceMismatchDialog("session", "project", "timestamp")
        self.assertEqual(
            dialog.choices,
            (SourceMismatchChoice.RESTORE_UNLINKED, SourceMismatchChoice.DISCARD),
        )


if __name__ == "__main__":
    unittest.main()
