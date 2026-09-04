from .models import Precondition


class TourEnvironment:
    """Read-only semantic precondition checker."""

    def check(self, precondition: Precondition) -> bool:
        raise NotImplementedError
