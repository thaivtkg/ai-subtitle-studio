from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class StartupContext:
    """Immutable startup facts supplied by the application entry point."""

    recovery: bool = False
    external_open: bool = False


def build_startup_context(sys_args: List[str], has_pending_recovery: bool) -> StartupContext:
    """
    Translate operating-system startup inputs into an immutable StartupContext.
    """
    return StartupContext(
        recovery=has_pending_recovery,
        external_open=len(sys_args) > 1,
    )
