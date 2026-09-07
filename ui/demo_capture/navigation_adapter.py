from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.ports import NavigationAdapterPort


class CaptureNavigationAdapter(NavigationAdapterPort):
    def __init__(self, production_router):
        self._router = production_router

    def navigate(self, destination: str) -> None:
        try:
            if callable(self._router):
                self._router(destination)
            elif hasattr(self._router, "navigate_to_route"):
                self._router.navigate_to_route(destination)
            else:
                raise RuntimeError("Unsupported router interface")
        except Exception as error:
            raise CaptureRunError(
                error_code=CaptureErrorCode.NAVIGATION_FAILED,
                message=f"Navigation to '{destination}' failed: {error}",
                target=destination,
            ) from error
