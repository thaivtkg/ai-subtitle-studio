import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.app_context import StartupContext
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus
from ui.Gui import MainWindow


class FakeProgressStoreE2E:
    def __init__(self, status=GuideProgressStatus.NOT_STARTED):
        self._status = status
        self.dismissed = False

    def status(self, guide_id: str, version: int = 1):
        return GuideProgress(self._status)

    def mark_dismissed(self, guide_id: str, version: int = 1):
        self.dismissed = True


class TestC2BootstrapPriorityE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def tearDown(self):
        self.app.processEvents()

    def _build_and_show_window(self, context):
        window = MainWindow(startup_context=context)
        window.show()
        self.app.processEvents()
        return window

    def _close_window(self, window):
        window.close()
        window.deleteLater()
        self.app.processEvents()

    @patch("ui.Gui.TourProgressStore")
    def test_bootstrap_clean_interactive_startup_shows_banner(self, mock_store):
        store = FakeProgressStoreE2E()
        mock_store.return_value = store
        window = self._build_and_show_window(
            StartupContext(recovery=False, external_open=False)
        )

        self.assertTrue(window.first_run_banner.isVisible())
        self.assertFalse(store.dismissed)
        self.assertEqual(store._status, GuideProgressStatus.NOT_STARTED)
        self._close_window(window)

    @patch("ui.Gui.TourProgressStore")
    def test_bootstrap_external_open_suppresses_banner(self, mock_store):
        store = FakeProgressStoreE2E()
        mock_store.return_value = store
        window = self._build_and_show_window(
            StartupContext(recovery=False, external_open=True)
        )

        self.assertFalse(window.first_run_banner.isVisible())
        self.assertFalse(store.dismissed)
        self.assertEqual(store._status, GuideProgressStatus.NOT_STARTED)
        self._close_window(window)

    @patch("ui.Gui.TourProgressStore")
    def test_bootstrap_recovery_suppresses_banner(self, mock_store):
        store = FakeProgressStoreE2E()
        mock_store.return_value = store
        window = self._build_and_show_window(
            StartupContext(recovery=True, external_open=False)
        )

        self.assertFalse(window.first_run_banner.isVisible())
        self.assertFalse(store.dismissed)
        self.assertEqual(store._status, GuideProgressStatus.NOT_STARTED)
        self._close_window(window)

    @patch("ui.Gui.TourProgressStore")
    def test_bootstrap_priority_recovery_over_external(self, mock_store):
        store = FakeProgressStoreE2E()
        mock_store.return_value = store
        window = self._build_and_show_window(
            StartupContext(recovery=True, external_open=True)
        )

        self.assertFalse(window.first_run_banner.isVisible())
        self.assertFalse(store.dismissed)
        self.assertEqual(store._status, GuideProgressStatus.NOT_STARTED)
        self._close_window(window)


if __name__ == "__main__":
    unittest.main()
