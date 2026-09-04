from collections.abc import Callable


class TourEnvironment:
    """Read-only semantic precondition checker backed by a delegate."""

    def __init__(self, checker: Callable[[str], bool]) -> None:
        self._checker = checker

    def check(self, precondition: str) -> bool:
        return bool(self._checker(precondition))
