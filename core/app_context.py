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

    (SCAFFOLD: intentionally hard-coded to establish the behavioral RED.)
    """
    return StartupContext(recovery=False, external_open=False)
