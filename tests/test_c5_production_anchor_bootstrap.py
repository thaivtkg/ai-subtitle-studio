import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from core.tutorial.models import AnchorStatus
from ui.Gui import MainWindow


class TestC5ProductionAnchorBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow(
            project_service=MagicMock(),
            media_import_service=MagicMock(),
        )
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def _assert_anchor_resolves_to(self, anchor_id, widget):
        resolution = self.window.tour_anchor_registry.resolve(anchor_id)
        self.assertEqual(resolution.status, AnchorStatus.RESOLVED, anchor_id)
        self.assertIs(self.window.tour_anchor_registry.get_widget(resolution.handle), widget)

    def test_production_semantic_anchors_resolve_to_live_widgets(self):
        self._assert_anchor_resolves_to("dashboard.root", self.window.page_dashboard)
        self._assert_anchor_resolves_to(
            "dashboard.new_project", self.window.btn_new_project
        )
        self._assert_anchor_resolves_to(
            "navigation.video_workspace", self.window.nav_btns[1]
        )

        self.window.switch_page(1)
        self.app.processEvents()
        self._assert_anchor_resolves_to(
            "workspace.subtitle_editor", self.window.sub_editor
        )
        self._assert_anchor_resolves_to(
            "workspace.ai_generation", self.window.generation_panel
        )

        self.window.switch_page(5)
        self.app.processEvents()
        self._assert_anchor_resolves_to(
            "export_center.root", self.window.page_export
        )


if __name__ == "__main__":
    unittest.main()
