import unittest
from dataclasses import FrozenInstanceError

from core.tutorial.catalog import parse_tour_definition
from core.tutorial.models import CalloutPlacement, TourStepType


class TestTourDefinitionParsing(unittest.TestCase):
    def _valid_payload(self):
        return {
            "schema_version": 1,
            "guide_id": "getting_started",
            "content_version": 1,
            "title": "Getting Started",
            "description": "Learn the basic workflow.",
            "category": "getting_started",
            "estimated_minutes": 3,
            "steps": [{
                "step_id": "intro",
                "type": "INFO",
                "surface": {"route": "dashboard"},
                "callout": {"title": "Welcome", "body": "This is the dashboard.", "placement": "auto"},
            }],
        }

    def test_tc132_parse_returns_frozen_definition(self):
        definition = parse_tour_definition(self._valid_payload())
        self.assertEqual(definition.guide_id, "getting_started")
        self.assertEqual(definition.steps[0].step_type, TourStepType.INFO)
        with self.assertRaises(FrozenInstanceError):
            definition.guide_id = "mutated"

    def test_tc133_missing_surface_is_none_for_engine_inheritance(self):
        payload = self._valid_payload()
        payload["steps"].append({
            "step_id": "same_surface", "type": "INFO",
            "callout": {"title": "Continue", "body": "Stay on the current surface.", "placement": "bottom"},
        })
        definition = parse_tour_definition(payload)
        self.assertIsNone(definition.steps[1].surface)

    def test_tc134_back_defaults_follow_step_type(self):
        payload = self._valid_payload()
        payload["steps"] = [
            {"step_id": "info", "type": "INFO", "callout": {"title": "I", "body": "I", "placement": "auto"}},
            {"step_id": "action", "type": "ACTION", "anchor": "demo.button", "interaction": {"kind": "CLICK"}, "callout": {"title": "A", "body": "A", "placement": "auto"}},
            {"step_id": "demo", "type": "DEMO", "demo": {"asset": "assets/demo.gif", "media_type": "ANIMATED_IMAGE", "fit": "contain"}, "callout": {"title": "D", "body": "D", "placement": "center"}},
        ]
        definition = parse_tour_definition(payload)
        self.assertTrue(definition.steps[0].safety.allow_back)
        self.assertFalse(definition.steps[1].safety.allow_back)
        self.assertTrue(definition.steps[2].safety.allow_back)

    def test_tc135_unknown_callout_placement_is_rejected(self):
        payload = self._valid_payload()
        payload["steps"][0]["callout"]["placement"] = "floating-anywhere"
        with self.assertRaises(ValueError):
            parse_tour_definition(payload)


if __name__ == "__main__":
    unittest.main()
