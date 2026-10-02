import json
import unittest
from pathlib import Path

from core.tutorial.catalog import TourCatalog
from core.tutorial.models import InteractionKind, TargetPolicy, TourStepType


class TestC5ProductionTourContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parents[1] / "resources" / "tutorials"
        cls.guide_path = cls.root / "getting_started.json"

    def _load(self):
        raw = json.loads(self.guide_path.read_text(encoding="utf-8"))
        catalog = TourCatalog(self.root)
        guides = catalog.load_all()
        self.assertEqual(catalog.errors, ())
        self.assertEqual([guide.guide_id for guide in guides], ["getting_started"])
        guide = catalog.get_guide("getting_started")
        self.assertIsNotNone(guide)
        return raw, guide

    def test_tc257_identity_order_and_step_types(self):
        raw, guide = self._load()
        expected_ids = [
            "welcome",
            "dashboard_overview",
            "create_project_entry",
            "open_video_workspace",
            "subtitle_editor_overview",
            "ai_workspace_overview",
            "generation_demo",
            "export_center_overview",
            "finish",
        ]
        expected_types = [
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.ACTION,
            TourStepType.INFO,
            TourStepType.INFO,
            TourStepType.DEMO,
            TourStepType.INFO,
            TourStepType.INFO,
        ]

        self.assertEqual(raw["guide_id"], "getting_started")
        self.assertEqual(raw["content_version"], 2)
        self.assertEqual(guide.content_version, 2)
        self.assertEqual([step.step_id for step in guide.steps], expected_ids)
        self.assertEqual([step.step_type for step in guide.steps], expected_types)
        self.assertEqual(len(guide.steps), 9)
        self.assertEqual(guide.preconditions, ())
        self.assertTrue(all(step.preconditions == () for step in guide.steps))

    def test_tc258_surfaces_anchors_policies_and_action_contract(self):
        _, guide = self._load()
        by_id = {step.step_id: step for step in guide.steps}

        self.assertEqual(by_id["welcome"].surface.route, "dashboard")
        self.assertEqual(by_id["dashboard_overview"].surface.route, "dashboard")
        self.assertEqual(by_id["create_project_entry"].surface.route, "dashboard")
        self.assertEqual(by_id["open_video_workspace"].surface.route, "dashboard")
        self.assertEqual(by_id["subtitle_editor_overview"].surface.route, "workspace")
        self.assertIsNone(by_id["subtitle_editor_overview"].surface.subroute)
        self.assertEqual(by_id["ai_workspace_overview"].surface.route, "workspace")
        self.assertEqual(by_id["ai_workspace_overview"].surface.subroute, "generate")
        self.assertEqual(by_id["generation_demo"].surface.route, "workspace")
        self.assertEqual(by_id["generation_demo"].surface.subroute, "generate")
        self.assertEqual(by_id["export_center_overview"].surface.route, "export_center")
        self.assertIsNone(by_id["finish"].surface)

        expected_anchors = {
            "dashboard_overview": "dashboard.root",
            "create_project_entry": "dashboard.new_project",
            "open_video_workspace": "navigation.video_workspace",
            "subtitle_editor_overview": "workspace.subtitle_editor",
            "ai_workspace_overview": "workspace.ai_generation",
            "export_center_overview": "export_center.root",
        }
        self.assertEqual(
            {step_id: by_id[step_id].anchor for step_id in expected_anchors},
            expected_anchors,
        )

        action = by_id["open_video_workspace"]
        self.assertEqual(action.target_policy, TargetPolicy.REQUIRED)
        self.assertEqual(action.interaction.kind, InteractionKind.CLICK)
        self.assertFalse(action.safety.allow_back)
        self.assertFalse(by_id["subtitle_editor_overview"].safety.allow_back)

        for step_id in (
            "dashboard_overview",
            "create_project_entry",
            "subtitle_editor_overview",
            "ai_workspace_overview",
            "export_center_overview",
        ):
            self.assertEqual(by_id[step_id].target_policy, TargetPolicy.FALLBACK_TO_INFO)

        self.assertEqual(
            [step.step_id for step in guide.steps if step.step_type is TourStepType.ACTION],
            ["open_video_workspace"],
        )

    def test_tc259_demo_source_and_runtime_contract(self):
        raw, guide = self._load()
        raw_demo = next(
            step["demo"] for step in raw["steps"] if step["step_id"] == "generation_demo"
        )
        runtime_demo = next(
            step.demo for step in guide.steps if step.step_id == "generation_demo"
        )

        self.assertEqual(raw_demo["asset"], "assets/getting_started_generation.gif")
        self.assertEqual(raw_demo["media_type"], "gif")
        self.assertEqual(raw_demo["fit"], "contain")
        self.assertEqual(runtime_demo.media_type, "gif")
        self.assertEqual(runtime_demo.fit, "contain")
        self.assertEqual(Path(runtime_demo.asset).name, "getting_started_generation.gif")
        self.assertEqual(Path(runtime_demo.asset).parent, (self.root / "assets").resolve())


if __name__ == "__main__":
    unittest.main()
