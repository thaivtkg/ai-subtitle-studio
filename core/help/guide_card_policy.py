from core.tutorial.models import TourDefinition
from core.tutorial.progress_store import GuideProgress, GuideProgressStatus
from .help_models import GuideCardViewModel


_PRESENTATION = {
    GuideProgressStatus.NOT_STARTED: ("New", "Start Tour"),
    GuideProgressStatus.COMPLETED: ("Completed", "Replay"),
    GuideProgressStatus.DISMISSED: ("Dismissed", "Start Tour"),
    GuideProgressStatus.OUTDATED: ("Updated", "Start Updated Tour"),
    GuideProgressStatus.COMPLETED_NEWER_VERSION: ("Completed", "Replay"),
    GuideProgressStatus.UNKNOWN: ("Progress unavailable", "Start Tour"),
}


def build_guide_card_view_model(
    guide: TourDefinition,
    progress: GuideProgress,
    *,
    enabled: bool = True,
    blocked_reason=None,
) -> GuideCardViewModel:
    badge, cta = _PRESENTATION.get(progress.status, ("Progress unavailable", "Start Tour"))
    return GuideCardViewModel(
        guide_id=guide.guide_id,
        title=guide.title,
        description=guide.description,
        category=guide.category,
        estimated_minutes=guide.estimated_minutes,
        badge=badge,
        cta=cta,
        enabled=enabled,
        blocked_reason=blocked_reason,
    )


__all__ = [
    "GuideCardViewModel",
    "build_guide_card_view_model",
]
