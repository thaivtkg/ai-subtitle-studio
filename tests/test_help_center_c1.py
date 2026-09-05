import unittest

from core.tutorial.models import TourDefinition
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus
from core.help.guide_card_policy import (
    GuideStartStatus,
    build_guide_card_view_model,
)
from core.help.help_center_controller import HelpCenterController


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
            (GuideProgressStatus.NOT_STARTED, GuideStartStatus.NEW, "Start Tour"),
            (GuideProgressStatus.COMPLETED, GuideStartStatus.COMPLETED, "Replay"),
            (GuideProgressStatus.DISMISSED, GuideStartStatus.DISMISSED, "Start Tour"),
            (GuideProgressStatus.OUTDATED, GuideStartStatus.UPDATED, "Start Updated Tour"),
            (
                GuideProgressStatus.COMPLETED_NEWER_VERSION,
                GuideStartStatus.COMPLETED,
                "Replay",
            ),
            (
                GuideProgressStatus.UNKNOWN,
                GuideStartStatus.UNKNOWN,
                "Start Tour",
            ),
        )

        for progress_status, expected_status, expected_action in cases:
            with self.subTest(progress_status=progress_status):
                view = build_guide_card_view_model(
                    guide(), GuideProgress(progress_status)
                )
                self.assertEqual(view.start.status, expected_status)
                self.assertEqual(view.start.action_label, expected_action)

    def test_tc174_preserves_guide_metadata_and_has_no_mutation(self):
        snapshot = GuideProgress(GuideProgressStatus.COMPLETED)
        view = build_guide_card_view_model(guide(), snapshot)

        self.assertEqual(view.guide_id, "getting_started")
        self.assertEqual(view.title, "Getting Started")
        self.assertEqual(view.description, "Learn the basics.")
        self.assertEqual(view.category, "Basics")
        self.assertEqual(view.estimated_minutes, 3)
        self.assertEqual(view.step_count, 0)
        self.assertEqual(snapshot, GuideProgress(GuideProgressStatus.COMPLETED))


class TestHelpCenterController(unittest.TestCase):
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
        controller = HelpCenterController(
            [guide(), other],
            lambda item: GuideProgress(GuideProgressStatus.NOT_STARTED),
            started.append,
        )

        self.assertEqual([card.guide_id for card in controller.cards], [
            "getting_started", "export"
        ])
        self.assertEqual(
            [card.guide_id for card in controller.search("TRANSLATED")],
            ["export"],
        )
        self.assertTrue(controller.start_guide("export"))
        self.assertEqual(started, [other])
        self.assertFalse(controller.start_guide("missing"))

    def test_tc176_debounces_search_and_publishes_only_latest_query(self):
        scheduled = []
        published = []
        controller = HelpCenterController(
            [guide()],
            lambda item: GuideProgress(GuideProgressStatus.NOT_STARTED),
            lambda item: None,
            published.append,
        )

        controller.schedule_search("get", lambda delay, callback: scheduled.append((delay, callback)))
        controller.schedule_search("started", lambda delay, callback: scheduled.append((delay, callback)))

        self.assertEqual([delay for delay, _ in scheduled], [175, 175])
        scheduled[0][1]()
        self.assertEqual(published, [])
        scheduled[1][1]()
        self.assertEqual([card.guide_id for card in published[0]], ["getting_started"])


if __name__ == "__main__":
    unittest.main()
