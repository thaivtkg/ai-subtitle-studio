from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from ui.tutorial.anchor_registry import AnchorStatus


class AnchorRegistryCaptureAdapter:
    """Map semantic AnchorRegistry resolution into the C4 capture contract."""

    def __init__(self, registry):
        self._registry = registry

    def resolve_widget(self, semantic_id: str):
        try:
            resolution = self._registry.resolve(semantic_id)
        except Exception as error:
            raise CaptureRunError(
                error_code=CaptureErrorCode.TARGET_RESOLUTION_ERROR,
                message=f"Resolution crashed for '{semantic_id}': {error}",
                target=semantic_id,
            ) from error

        if resolution.status == AnchorStatus.RESOLVED:
            widget = self._registry.get_widget(resolution.handle)
            if widget is None:
                raise CaptureRunError(
                    error_code=CaptureErrorCode.TARGET_INVALID,
                    message=f"Target '{semantic_id}' is resolved but widget is None",
                    target=semantic_id,
                )
            return widget

        if resolution.status == AnchorStatus.NOT_FOUND:
            raise CaptureRunError(
                error_code=CaptureErrorCode.TARGET_NOT_FOUND,
                message=f"Target '{semantic_id}' not found in registry",
                target=semantic_id,
            )

        if resolution.status == AnchorStatus.NOT_VISIBLE:
            raise CaptureRunError(
                error_code=CaptureErrorCode.TARGET_NOT_VISIBLE,
                message=f"Target '{semantic_id}' is registered but not visible",
                target=semantic_id,
            )

        if resolution.status == AnchorStatus.INVALID:
            raise CaptureRunError(
                error_code=CaptureErrorCode.TARGET_INVALID,
                message=f"Target '{semantic_id}' is invalid (e.g. destroyed)",
                target=semantic_id,
            )

        raise CaptureRunError(
            error_code=CaptureErrorCode.TARGET_RESOLUTION_ERROR,
            message=f"Unknown anchor status for '{semantic_id}': {resolution.status}",
            target=semantic_id,
        )
