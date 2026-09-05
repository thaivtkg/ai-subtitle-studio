from .help_models import GuideCardViewModel, GuideStartResult, GuideStartStatus


_PRESENTATION = {
    "NOT_STARTED": (GuideStartStatus.NEW, "New", "Start Tour"),
    "COMPLETED": (GuideStartStatus.COMPLETED, "Completed", "Replay"),
    "DISMISSED": (GuideStartStatus.DISMISSED, "Dismissed", "Start Tour"),
    "OUTDATED": (GuideStartStatus.UPDATED, "Updated", "Start Updated Tour"),
    "COMPLETED_NEWER_VERSION": (GuideStartStatus.COMPLETED, "Completed", "Replay"),
    "UNKNOWN": (GuideStartStatus.UNKNOWN, "Progress unavailable", "Start Tour"),
}


def build_guide_card_view_model(guide, progress) -> GuideCardViewModel:
    status, status_label, action_label = _PRESENTATION[progress.status.value]
    return GuideCardViewModel(
        guide_id=guide.guide_id,
        title=guide.title,
        description=guide.description,
        category=guide.category,
        estimated_minutes=guide.estimated_minutes,
        step_count=len(guide.steps),
        start=GuideStartResult(status, status_label, action_label),
    )


__all__ = [
    "GuideCardViewModel",
    "GuideStartResult",
    "GuideStartStatus",
    "build_guide_card_view_model",
]
