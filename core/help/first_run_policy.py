from enum import Enum


class FirstRunDecision(str, Enum):
    SHOW_BANNER = "SHOW_BANNER"
    DO_NOTHING = "DO_NOTHING"


def evaluate_startup(
    progress_store,
    guide_id,
    content_version=1,
    *,
    external_open=False,
    recovery=False,
    workflow_started=False,
):
    """C2 RED scaffold; startup behavior is intentionally not implemented yet."""
    return FirstRunDecision.DO_NOTHING


def dismiss_first_run(progress_store, guide_id, content_version):
    """C2 RED scaffold for explicit banner dismissal."""


def start_first_run(progress_store, guide_id, content_version, start_tour):
    """C2 RED scaffold for dismiss-before-start ordering."""
    return False


def complete_first_run(progress_store, guide_id, content_version):
    """C2 RED scaffold for completion persistence."""
