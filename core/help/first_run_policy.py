from enum import Enum
from typing import Any, Callable

from core.tutorial.progress_store import GuideProgressStatus


class FirstRunDecision(str, Enum):
    SHOW_BANNER = "SHOW_BANNER"
    DO_NOTHING = "DO_NOTHING"


def evaluate_startup(
    progress_store: Any,
    guide_id: str,
    content_version: int = 1,
    *,
    external_open: bool = False,
    recovery: bool = False,
    workflow_started: bool = False,
) -> FirstRunDecision:
    """Decide whether the non-blocking first-run banner should be shown."""
    if external_open or recovery or workflow_started:
        return FirstRunDecision.DO_NOTHING
    try:
        progress = progress_store.status(guide_id, content_version)
        if progress.status == GuideProgressStatus.NOT_STARTED:
            return FirstRunDecision.SHOW_BANNER
    except Exception:
        pass
    return FirstRunDecision.DO_NOTHING


def dismiss_first_run(
    progress_store: Any, guide_id: str, content_version: int = 1
) -> None:
    """Persist an explicit first-run banner dismissal when supported."""
    if hasattr(progress_store, "mark_dismissed"):
        progress_store.mark_dismissed(guide_id, content_version)


def start_first_run(
    progress_store: Any,
    guide_id: str,
    content_version: int,
    start_tour_fn: Callable[[str], bool],
) -> bool:
    """Persist dismissal before starting the first-run tour."""
    dismiss_first_run(progress_store, guide_id, content_version)
    return start_tour_fn(guide_id) if start_tour_fn else False


def complete_first_run(
    progress_store: Any, guide_id: str, content_version: int = 1
) -> None:
    """Persist completion when the caller does not use TourEngine persistence."""
    if hasattr(progress_store, "mark_completed"):
        progress_store.mark_completed(guide_id, content_version)
