import unittest

from core.tutorial.models import Precondition, TourDefinition
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus
from core.help.guide_card_policy import build_guide_card_view_model
from core.help.help_center_controller import HelpCenterController
from core.help.help_models import GuideStartStatus


def guide():
    return TourDefinition(
        schema_version=1,
        guide_id="getting_started",
        content_version=2,
        title="Getting Started",
        category="Basics",
        estimated_minutes=3,
        description="Learn the basics.",
        steps=(),
    )


class TestGuideCardPolicy(unittest.TestCase):
    def test_tc174_maps_progress_to_status_and_action(self):
        cases = (
            (GuideProgressStatus.NOT_STARTED, "New", "Start Tour"),
            (GuideProgressStatus.COMPLETED, "Completed", "Replay"),
            (GuideProgressStatus.DISMISSED, "Dismissed", "Start Tour"),
            (GuideProgressStatus.OUTDATED, "Updated", "Start Updated Tour"),
            (
                GuideProgressStatus.COMPLETED_NEWER_VERSION,
                "Completed",
                "Replay",
            ),
            (
                GuideProgressStatus.UNKNOWN,
                "Progress unavailable",
                "Start Tour",
            ),
        )

        for progress_status, expected_status, expected_action in cases:
            with self.subTest(progress_status=progress_status):
                view = build_guide_card_view_model(
                    guide(), GuideProgress(progress_status)
                )
                self.assertEqual(view.badge, expected_status)
                self.assertEqual(view.cta, expected_action)

    def test_tc174_preserves_guide_metadata_and_has_no_mutation(self):
        snapshot = GuideProgress(GuideProgressStatus.COMPLETED)
        view = build_guide_card_view_model(guide(), snapshot)

        self.assertEqual(view.guide_id, "getting_started")
        self.assertEqual(view.title, "Getting Started")
        self.assertEqual(view.description, "Learn the basics.")
        self.assertEqual(view.category, "Basics")
        self.assertEqual(view.estimated_minutes, 3)
        self.assertEqual(view.badge, "Completed")
        self.assertEqual(view.cta, "Replay")
        self.assertTrue(view.enabled)
        self.assertIsNone(view.blocked_reason)
        self.assertEqual(snapshot, GuideProgress(GuideProgressStatus.COMPLETED))


class TestHelpCenterController(unittest.TestCase):
    def test_tc175_missing_precondition_blocks_engine_start(self):
        blocked = TourDefinition(
            schema_version=1, guide_id="blocked", content_version=1,
            title="Blocked", category="Basics", estimated_minutes=1,
            description="", steps=(), preconditions=(Precondition.PROJECT_OPEN,),
        )
        class Catalog:
            def get_guide(self, guide_id): return blocked if guide_id == "blocked" else None
        class Store:
            def status(self, guide_id, version): return GuideProgress(GuideProgressStatus.NOT_STARTED)
        class Environment:
            def check(self, key): return False
        started = []
        controller = HelpCenterController(
            Catalog(), Store(), Environment(), start_tour_fn=lambda guide_id: started.append(guide_id),
        )

        result = controller.start_guide("blocked")

        self.assertEqual(result.status, GuideStartStatus.PRECONDITION_FAILED)
        self.assertEqual(started, [])

    def test_tc175_lists_cards_searches_locally_and_starts_selected_guide(self):
        started = []
        other = TourDefinition(
            schema_version=1,
            guide_id="export",
            content_version=1,
            title="Export subtitles",
            category="Output",
            estimated_minutes=2,
            description="Save your translated subtitles.",
            steps=(),
        )
        class Catalog:
            def __init__(self):
                self.guides = {item.guide_id: item for item in (guide(), other)}
            def all_guides(self): return tuple(self.guides.values())
            def get_guide(self, guide_id): return self.guides.get(guide_id)
        class Environment:
            def check(self, _key): return True
        class ProgressStore:
            def status(self, guide_id, version):
                return GuideProgress(GuideProgressStatus.NOT_STARTED)
        controller = HelpCenterController(
            Catalog(), ProgressStore(),
            Environment(), start_tour_fn=lambda guide_id: started.append(guide_id) or True,
        )

        self.assertEqual([card.guide_id for card in controller.build_guide_cards()], [
            "getting_started", "export"
        ])
        self.assertEqual(controller.search("TRANSLATED")[0].item_id, "export")
        self.assertEqual(controller.start_guide("export").status, GuideStartStatus.READY)
        self.assertEqual(started, ["export"])
        self.assertEqual(controller.start_guide("missing").status, GuideStartStatus.START_FAILED)

    def test_tc176_debounces_search_and_publishes_only_latest_query(self):
        scheduled = []
        published = []
        self.skipTest("Debounce is a Qt page concern; covered by C1 UI gate")


if __name__ == "__main__":
    unittest.main()
