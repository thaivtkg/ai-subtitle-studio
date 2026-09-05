import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from core.help.help_models import (
    GuideCardViewModel,
    HelpSearchResult,
    SearchResultType,
)
from ui.help.shortcut_provider import RuntimeShortcutProvider
from ui.pages.help_center_page import HelpCenterPage
from ui.Gui import MainWindow
from ui.tutorial.navigation_adapter import MainWindowRouter, NavigationAdapter


class TestHelpCenterC1RuntimeShortcutProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_runtime_tour_uses_navigation_adapter_port(self):
        window = MainWindow(
            project_service=MagicMock(), media_import_service=MagicMock()
        )
        self.assertIsInstance(window.tour_router, MainWindowRouter)
        self.assertIsInstance(window.tour_navigation, NavigationAdapter)
        self.assertIs(window.tour_engine._navigation, window.tour_navigation)
        window.deleteLater()
        self.app.processEvents()

    def test_tc177_reads_current_shortcuts_and_reflects_key_changes(self):
        window = QWidget()
        shortcut = QShortcut(QKeySequence("Ctrl+S"), window)
        provider = RuntimeShortcutProvider(window)
        provider.register_shortcut(shortcut, "save", "Save", "Global")

        self.assertEqual(provider.get_shortcuts()[0].sequence, "Ctrl+S")
        shortcut.setKey(QKeySequence("Ctrl+Shift+S"))
        self.app.processEvents()
        self.assertEqual(provider.get_shortcuts()[0].sequence, "Ctrl+Shift+S")
        window.deleteLater()
        self.app.processEvents()

    def test_help_page_debounces_and_latest_query_wins(self):
        cards = (
            GuideCardViewModel("first", "First", "First guide", "Basics", 1, "New", "Start Tour"),
            GuideCardViewModel("second", "Second", "Second guide", "Basics", 1, "New", "Start Tour"),
        )

        class Controller:
            def __init__(self):
                self.queries = []

            def build_guide_cards(self):
                return cards

            def search(self, query):
                self.queries.append(query)
                return (HelpSearchResult(SearchResultType.GUIDE, query, query.title(), "", "Basics"),)

            def start_guide(self, _guide_id):
                return SimpleNamespace(status=SimpleNamespace(value="READY"), reason=None)

        controller = Controller()
        page = HelpCenterPage(controller, None)
        page._search.setText("first")
        page._search.setText("second")
        QTest.qWait(220)
        self.assertEqual(controller.queries, ["second"])
        self.assertIn("Second", [label.text() for label in page._cards.findChildren(QLabel)])
        page.deleteLater()
        self.app.processEvents()

    def test_help_page_empty_query_renders_card_and_disabled_cta(self):
        card = GuideCardViewModel("blocked", "Blocked", "Needs a project", "Basics", 1, "New", "Start Tour", False, "Precondition failed")

        class Controller:
            def __init__(self):
                self.started = []

            def build_guide_cards(self):
                return (card,)

            def search(self, _query):
                return ()

            def start_guide(self, guide_id):
                self.started.append(guide_id)
                return SimpleNamespace(status=SimpleNamespace(value="READY"), reason=None)

        controller = Controller()
        page = HelpCenterPage(controller, None)
        buttons = page._cards.findChildren(QPushButton)
        self.assertEqual([button.text() for button in buttons], ["Start Tour"])
        self.assertFalse(buttons[0].isEnabled())
        buttons[0].click()
        self.assertEqual(controller.started, [])
        page.deleteLater()
        self.app.processEvents()

    def test_help_page_cta_starts_selected_guide_once(self):
        card = GuideCardViewModel("guide", "Guide", "Description", "Basics", 1, "New", "Start Tour")

        class Controller:
            def __init__(self):
                self.started = []

            def build_guide_cards(self):
                return (card,)

            def start_guide(self, guide_id):
                self.started.append(guide_id)
                return SimpleNamespace(status=SimpleNamespace(value="READY"), reason=None)

        controller = Controller()
        page = HelpCenterPage(controller, None)
        requested = []
        page.start_guide_requested.connect(requested.append)
        page._cards.findChildren(QPushButton)[0].click()
        self.assertEqual(controller.started, ["guide"])
        self.assertEqual(requested, ["guide"])
        page.deleteLater()
        self.app.processEvents()

    def test_main_window_help_navigation_f1_and_semantic_shortcuts(self):
        window = MainWindow(project_service=MagicMock(), media_import_service=MagicMock())
        window.shortcut_help.activated.emit()
        self.assertEqual(window._active_nav_index, 7)
        self.assertEqual(window.stack.currentIndex(), 6)
        window.tour_engine.start = MagicMock()
        window.shortcut_help.activated.emit()
        window.tour_engine.start.assert_not_called()
        shortcuts = {item.action_id: item for item in window.shortcut_provider.get_shortcuts()}
        self.assertEqual(shortcuts["save_project"].sequence, "Ctrl+S")
        self.assertEqual(shortcuts["open_project"].sequence, "Ctrl+O")
        self.assertEqual(shortcuts["help.center"].sequence, "F1")
        window.shortcut_save.setKey(QKeySequence("Ctrl+Shift+S"))
        self.app.processEvents()
        self.assertEqual(
            {item.action_id: item for item in window.shortcut_provider.get_shortcuts()}[
                "save_project"
            ].sequence,
            "Ctrl+Shift+S",
        )
        window.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
