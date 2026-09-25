import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from ui.Gui import MainWindow


class _CanonicalPresentation:
    def __init__(self, status="Saved", countdown=""):
        self.enabled = True
        self.delay_ms = 1000
        self.status = status
        self.countdown = countdown

    def status_text(self):
        return self.status

    def countdown_text(self):
        return self.countdown

    def flush_now(self):
        return True

    def dispose(self):
        return None


class ProjectStatusTitlebarIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.project_service = MagicMock()
        self.project_service.current_project = None
        self.project_service.project_dir = None
        with patch(
            "ui.subtitle_generation_panel.SubtitleGenerationPanel.check_resumable_state"
        ):
            self.window = MainWindow(
                project_service=self.project_service,
                media_import_service=MagicMock(),
            )
        self.window.canonical_save_coordinator = _CanonicalPresentation()
        self.addCleanup(self.window.close)

    def refresh(self, project=None, project_dir=None, *, status="Saved", countdown=""):
        self.project_service.current_project = project
        self.project_service.project_dir = project_dir
        self.window.canonical_save_coordinator = _CanonicalPresentation(
            status, countdown
        )
        self.window._update_canonical_save_status()
        self.app.processEvents()

    def test_PSI01_project_status_label_is_in_topbar_without_replacing_page_title(self):
        label = self.window.findChild(QLabel, "lbl_project_status")

        self.assertIsNotNone(label)
        self.assertEqual(label.parent().objectName(), "TopbarFrame")
        self.assertIsNot(self.window.lbl_page_title, label)

    def test_PSI02_titlebar_uses_current_project_and_shared_countdown_source(self):
        project = SimpleNamespace(name="Project A", project_id="project-a")

        self.refresh(project, r"D:\Temp\Project A.ai-subtitle", countdown="Save in 0.8s")

        self.assertEqual(self.window.lbl_project_status.text(), "Project A · Save in 0.8s")

    def test_PSI03_failed_switch_presents_actual_project_or_no_project(self):
        project_a = SimpleNamespace(name="Project A", project_id="project-a")

        self.refresh(project_a, r"D:\Temp\Project A.ai-subtitle", status="Save failed")
        self.assertEqual(self.window.lbl_project_status.text(), "Project A · Save failed")

        self.refresh(None, None, status="Save failed")
        self.assertEqual(self.window.lbl_project_status.text(), "No Project")

    def test_PSI04_dirty_revision_race_does_not_present_saved(self):
        project = SimpleNamespace(name="Project A", project_id="project-a")

        self.refresh(project, r"D:\Temp\Project A.ai-subtitle", status="Unsaved")

        self.assertNotIn("Saved", self.window.lbl_project_status.text())
        self.assertEqual(self.window.lbl_project_status.text(), "Project A · Unsaved")

    def test_PSI05_long_name_is_elided_and_full_text_is_tooltip(self):
        project = SimpleNamespace(
            name="Very_Long_Project_Name_For_Layout_Validation",
            project_id="project-long",
        )
        full_text = f"{project.name} · Saved"

        self.refresh(project, r"D:\Temp\long.ai-subtitle")

        label = self.window.lbl_project_status
        self.assertNotEqual(label.text(), full_text)
        self.assertIn("…", label.text())
        self.assertEqual(label.toolTip(), full_text)
        self.assertLessEqual(label.maximumWidth(), 280)

    def test_PSI06_short_name_never_progressively_elides(self):
        project = SimpleNamespace(name="da", project_id="project-da")
        label = self.window.lbl_project_status
        label.resize(24, label.height())

        for _ in range(30):
            self.refresh(project, r"D:\Temp\da.ai-subtitle")
            self.assertEqual(label.text(), "da · Saved")

    def test_PSI07_repeated_project_switch_presentation_is_stable(self):
        projects = (
            SimpleNamespace(name="Project A", project_id="project-a"),
            SimpleNamespace(name="Project B", project_id="project-b"),
        )
        label = self.window.lbl_project_status
        label.resize(32, label.height())

        for index in range(40):
            project = projects[index % 2]
            for _ in range(3):
                self.refresh(
                    project,
                    rf"D:\Temp\{project.name}.ai-subtitle",
                )
                self.assertEqual(
                    self.window.lbl_project_status.text(),
                    f"{project.name} · Saved",
                )

    def test_PSI08_long_name_elision_is_stable(self):
        project = SimpleNamespace(
            name="Very_Long_Project_Name_For_Layout_Validation",
            project_id="project-long",
        )
        full_text = f"{project.name} · Saved"
        self.refresh(project, r"D:\Temp\long.ai-subtitle")
        visible = self.window.lbl_project_status.text()
        self.window.lbl_project_status.resize(40, self.window.lbl_project_status.height())

        for _ in range(30):
            self.refresh(project, r"D:\Temp\long.ai-subtitle")
            current = self.window.lbl_project_status.text()
            self.assertIn("…", current)
            self.assertEqual(self.window.lbl_project_status.toolTip(), full_text)
            self.assertEqual(current, visible)

    def test_PSI09_clear_queue_immediately_presents_no_project(self):
        project = SimpleNamespace(name="Project A", project_id="project-a")
        self.project_service.current_project = project
        self.project_service.project_dir = r"D:\Temp\Project A.ai-subtitle"

        def close_project():
            self.project_service.current_project = None
            self.project_service.project_dir = None

        self.project_service.close_project.side_effect = close_project
        self.window.recovery_manager.finalize_clean_shutdown = MagicMock()
        self.window.clear_files()

        self.assertIsNone(self.project_service.current_project)
        self.assertIsNone(self.project_service.project_dir)
        self.assertEqual(self.window.lbl_project_status.text(), "No Project")


if __name__ == "__main__":
    unittest.main()
