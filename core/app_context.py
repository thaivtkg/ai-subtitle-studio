from dataclasses import dataclass


@dataclass(frozen=True)
class StartupContext:
    """Immutable startup facts supplied by the application entry point."""

    recovery: bool = False
    external_open: bool = False
