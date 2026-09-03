from typing import Any, Mapping, Optional

from .models import (
    CalloutPlacement, CalloutSpec, DemoSpec, InteractionKind, InteractionSpec,
    SafetySpec, SurfaceSpec, TargetPolicy, TourDefinition, TourStep, TourStepType,
)


def _parse_surface(data: Optional[Mapping[str, Any]]) -> Optional[SurfaceSpec]:
    return None if data is None else SurfaceSpec(route=data.get("route", ""), subroute=data.get("subroute"))


def _parse_callout(data: Mapping[str, Any]) -> CalloutSpec:
    return CalloutSpec(data.get("title", ""), data.get("body", ""), CalloutPlacement(data.get("placement", "auto")))


def _parse_safety(data: Mapping[str, Any], step_type: TourStepType) -> SafetySpec:
    default_back = step_type is not TourStepType.ACTION
    return SafetySpec(data.get("allow_back", default_back), data.get("allow_skip_step", True), data.get("allow_skip_tour", True))


def _parse_step(data: Mapping[str, Any]) -> TourStep:
    step_type = TourStepType(data["type"])
    interaction_data = data.get("interaction")
    demo_data = data.get("demo")
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
