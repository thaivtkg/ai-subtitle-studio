import logging
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Optional

from .models import (
    CalloutPlacement, CalloutSpec, DemoSpec, InteractionKind, InteractionSpec,
    SafetySpec, SurfaceSpec, TargetPolicy, TourDefinition, TourStep, TourStepType,
)

logger = logging.getLogger(__name__)
_FORBIDDEN_STEP_KEYS = frozenset(("execute", "callback", "signal"))


def _parse_surface(data: Optional[Mapping[str, Any]]) -> Optional[SurfaceSpec]:
    return None if data is None else SurfaceSpec(route=data.get("route", ""), subroute=data.get("subroute"))


def _parse_callout(data: Mapping[str, Any]) -> CalloutSpec:
    return CalloutSpec(data.get("title", ""), data.get("body", ""), CalloutPlacement(data.get("placement", "auto")))


def _validate_asset_path(asset: Any) -> str:
    if not isinstance(asset, str) or not asset:
        raise ValueError("DEMO step requires a valid local asset path")
    posix = PurePosixPath(asset)
    windows = PureWindowsPath(asset)
    if posix.is_absolute() or windows.is_absolute() or any(part == ".." for part in (*posix.parts, *windows.parts)):
        raise ValueError(f"Asset path traversal detected: {asset}")
    return asset


def _parse_safety(data: Mapping[str, Any], step_type: TourStepType) -> SafetySpec:
    default_back = step_type is not TourStepType.ACTION
    return SafetySpec(data.get("allow_back", default_back), data.get("allow_skip_step", True), data.get("allow_skip_tour", True))


def _parse_step(data: Mapping[str, Any]) -> TourStep:
    forbidden = _FORBIDDEN_STEP_KEYS.intersection(data)
    if forbidden:
        raise ValueError(f"Step contains forbidden executable fields: {sorted(forbidden)}")
    step_type = TourStepType(data["type"])
    interaction_data = data.get("interaction")
    demo_data = data.get("demo")
    if demo_data is not None:
        demo_data = dict(demo_data)
        demo_data["asset"] = _validate_asset_path(demo_data.get("asset", ""))
    return TourStep(
        step_id=data.get("step_id", ""),
        step_type=step_type,
        callout=_parse_callout(data.get("callout", {})),
        surface=_parse_surface(data.get("surface")),
        anchor=data.get("anchor"),
        target_policy=TargetPolicy(data.get("target_policy", "FALLBACK_TO_INFO")),
        interaction=None if interaction_data is None else InteractionSpec(InteractionKind(interaction_data.get("kind", ""))),
        demo=None if demo_data is None else DemoSpec(demo_data.get("asset", ""), demo_data.get("media_type", ""), demo_data.get("fit", "contain")),
        safety=_parse_safety(data.get("safety", {}), step_type),
    )


def parse_tour_definition(payload: Mapping[str, object]) -> TourDefinition:
    return TourDefinition(
        schema_version=payload.get("schema_version", 1),
        guide_id=payload.get("guide_id", ""),
        content_version=payload.get("content_version", 1),
        title=payload.get("title", ""),
        description=payload.get("description", ""),
        category=payload.get("category", ""),
        estimated_minutes=payload.get("estimated_minutes", 0),
        steps=tuple(_parse_step(step) for step in payload.get("steps", [])),
    )


class TourParser:
    @staticmethod
    def parse_guide(data: Mapping[str, object]) -> TourDefinition:
        return parse_tour_definition(data)


class TourCatalog:
    def __init__(self) -> None:
        self._guides: dict[str, TourDefinition] = {}

    def load(self, guides_data: Iterable[Mapping[str, object]]) -> None:
        for data in guides_data:
            guide_id = data.get("guide_id", "unknown_guide")
            try:
                guide = TourParser.parse_guide(data)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error("[TOUR] Catalog load failed for guide %r: %s", guide_id, exc)
                continue
            if guide.guide_id in self._guides:
                logger.warning("Duplicate guide_id detected: %s. Skipping.", guide.guide_id)
                continue
            self._guides[guide.guide_id] = guide

    def get_guide(self, guide_id: str) -> Optional[TourDefinition]:
        return self._guides.get(guide_id)

    def get_all_guides(self) -> list[TourDefinition]:
        return list(self._guides.values())
