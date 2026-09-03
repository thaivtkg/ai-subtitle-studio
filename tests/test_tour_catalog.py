import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from core.tutorial.catalog import TourCatalog, TourParser, parse_tour_definition
from core.tutorial.models import CalloutSpec, TourStep, TourStepType


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

    def test_tour_step_requires_explicit_safety(self):
        with self.assertRaises(TypeError):
            TourStep(step_id="open", step_type=TourStepType.ACTION, callout=CalloutSpec("T", "T"))

    def test_tc136_reject_executable_fields(self):
        for field in ("execute", "callback", "signal"):
            payload = {"schema_version": 1, "guide_id": "unsafe", "steps": [{
                "step_id": "1", "type": "INFO", field: "dangerous", "callout": {},
            }]}
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "forbidden executable fields"):
                    TourParser.parse_guide(payload)

    def test_tc137_reject_asset_path_traversal_and_absolute_paths(self):
        for asset in ("../hacked.gif", "assets/../hacked.gif", "/var/run/secret.gif", "C:\\secret.gif"):
            payload = {"schema_version": 1, "guide_id": "unsafe", "steps": [{
                "step_id": "1", "type": "DEMO", "demo": {"asset": asset}, "callout": {},
            }]}
            with self.subTest(asset=asset):
                with self.assertRaisesRegex(ValueError, "path traversal detected"):
                    TourParser.parse_guide(payload)


class TestTourCatalog(unittest.TestCase):
    def test_tc137_filesystem_confinement(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = TourCatalog(Path(directory))
            with self.assertRaisesRegex(ValueError, "Guide path traversal detected"):
                catalog.load_guide("../outside.json")

    def test_tc138_catalog_fault_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "valid.json").write_text(json.dumps({
                "schema_version": 1, "guide_id": "valid",
                "steps": [{"step_id": "1", "type": "INFO", "callout": {}}],
            }), encoding="utf-8")
            (root / "invalid.json").write_text(json.dumps({"schema_version": 99, "steps": []}), encoding="utf-8")
            (root / "catalog.json").write_text(json.dumps({"guides": ["valid.json", "invalid.json", "missing.json"]}), encoding="utf-8")

            catalog = TourCatalog(root)
            guides = catalog.load_all()

            self.assertEqual([guide.guide_id for guide in guides], ["valid"])
            self.assertEqual(len(catalog.errors), 2)
            self.assertTrue(any("Unsupported schema_version" in error for error in catalog.errors))
            self.assertTrue(any("Guide file not found" in error for error in catalog.errors))


if __name__ == "__main__":
    unittest.main()
