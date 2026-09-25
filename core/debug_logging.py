from dataclasses import dataclass, field
from typing import Callable


DEBUG_CATEGORIES = frozenset(
    {
        "recovery",
        "canonical_save",
        "project_switch",
        "project_status",
        "waveform",
        "artifact_sync",
    }
)


@dataclass
class DebugConfig:
    master_enabled: bool = False
    enabled_categories: set[str] = field(default_factory=set)


def debug_enabled(category: str, config: DebugConfig) -> bool:
    return (
        config.master_enabled
        and category in DEBUG_CATEGORIES
        and category in config.enabled_categories
    )


def debug_log(
    category: str,
    message: str,
    config: DebugConfig,
    emit: Callable[[tuple[str, str, str]], None],
) -> bool:
    if not debug_enabled(category, config):
        return False
    emit(("DEBUG", category, message))
    return True


def warning_log(
    category: str,
    message: str,
    config: DebugConfig,
    emit: Callable[[tuple[str, str, str]], None],
) -> None:
    del config
    emit(("WARNING", category, message))


def error_log(
    category: str,
    message: str,
    config: DebugConfig,
    emit: Callable[[tuple[str, str, str]], None],
) -> None:
    del config
    emit(("ERROR", category, message))
