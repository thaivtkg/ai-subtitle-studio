import unittest
from types import SimpleNamespace

from ui.project_status import format_project_status


class ProjectStatusContracts(unittest.TestCase):
    def test_PS01_no_project_has_no_saved_suffix(self):
        self.assertEqual(format_project_status(None, "Saved"), "No Project")

    def test_PS02_project_name_is_primary_display_name(self):
        project = SimpleNamespace(name="Project A", project_id="id-a")

        self.assertEqual(format_project_status(project, "Saved"), "Project A · Saved")

    def test_PS03_save_status_comes_from_canonical_presentation_text(self):
        project = SimpleNamespace(name="Project A", project_id="id-a")

        for status in ("Saved", "Unsaved", "Save in 0.5s", "Saving…", "Save failed"):
            with self.subTest(status=status):
                self.assertEqual(format_project_status(project, status), f"Project A · {status}")

    def test_PS04_fallback_name_uses_project_root_without_suffix(self):
        project = SimpleNamespace(name="", project_id="id-a")

        self.assertEqual(
            format_project_status(project, "Saved", project_root="D:/Temp/da.ai-subtitle"),
            "da · Saved",
        )

    def test_PS05_fallback_name_does_not_use_video_name(self):
        project = SimpleNamespace(name="", project_id="id-a")

        self.assertEqual(
            format_project_status(
                project,
                "Saved",
                project_root="D:/Temp/da.ai-subtitle",
                video_path="D:/Videos/other-name.mp4",
            ),
            "da · Saved",
        )

    def test_PS06_failed_save_status_remains_on_source_project(self):
        project = SimpleNamespace(name="Project A", project_id="id-a")

        self.assertEqual(format_project_status(project, "Save failed"), "Project A · Save failed")

    def test_PS07_no_project_after_failed_target_open_is_not_target_name(self):
        self.assertEqual(format_project_status(None, "Save failed"), "No Project")

    def test_PS08_same_video_projects_use_actual_project_name(self):
        project_a = SimpleNamespace(name="A", project_id="id-a")
        project_b = SimpleNamespace(name="B", project_id="id-b")

        self.assertEqual(format_project_status(project_a, "Saved", video_path="same.mp4"), "A · Saved")
        self.assertEqual(format_project_status(project_b, "Saved", video_path="same.mp4"), "B · Saved")


if __name__ == "__main__":
    unittest.main()
