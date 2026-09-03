import json
import logging
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping, Optional

from .models import (
    CalloutPlacement, CalloutSpec, DemoSpec, InteractionKind, InteractionSpec,
    SafetySpec, SurfaceSpec, TargetPolicy, TourDefinition, TourStep, TourStepType, Precondition,
)

logger = logging.getLogger(__name__)
_ALLOWED_ROOT_KEYS = frozenset({"schema_version", "guide_id", "content_version", "title", "description", "category", "estimated_minutes", "steps", "preconditions"})
_ALLOWED_STEP_KEYS = frozenset({"step_id", "type", "surface", "anchor", "target_policy", "callout", "interaction", "demo", "safety", "preconditions"})
_ALLOWED_SURFACE_KEYS = frozenset(("route", "subroute"))
_ALLOWED_CALLOUT_KEYS = frozenset(("title", "body", "placement"))
_ALLOWED_INTERACTION_KEYS = frozenset(("kind",))
_ALLOWED_DEMO_KEYS = frozenset(("asset", "media_type", "fit"))
_ALLOWED_SAFETY_KEYS = frozenset(("allow_back", "allow_skip_step", "allow_skip_tour"))
_FORBIDDEN_STEP_KEYS = frozenset({"execute", "callback", "signal"})


def _parse_surface(data: Optional[Mapping[str, Any]]) -> Optional[SurfaceSpec]:
    return None if data is None else SurfaceSpec(route=data.get("route", ""), subroute=data.get("subroute"))


def _parse_callout(data: Mapping[str, Any]) -> CalloutSpec:
    if not isinstance(data, Mapping) or set(data) - _ALLOWED_CALLOUT_KEYS:
        raise ValueError("Unknown keys in callout object")
    return CalloutSpec(data.get("title", ""), data.get("body", ""), CalloutPlacement(data.get("placement", "auto")))


def _parse_safety(data: Mapping[str, Any], step_type: TourStepType) -> SafetySpec:
    return SafetySpec(data.get("allow_back", step_type is not TourStepType.ACTION), data.get("allow_skip_step", True), data.get("allow_skip_tour", True))


def _validate_asset_path(asset: Any, root: Path) -> str:
    if not isinstance(asset, str) or not asset:
        raise ValueError("DEMO step requires a valid local asset path")
    posix, windows = PurePosixPath(asset), PureWindowsPath(asset)
    if posix.is_absolute() or windows.is_absolute() or any(part == ".." for part in (*posix.parts, *windows.parts)):
        raise ValueError(f"Asset path traversal detected: {asset}")
    assets_dir = (root / "assets").resolve()
    candidate = (root / asset).resolve()
    if candidate != assets_dir and assets_dir not in candidate.parents:
        raise ValueError(f"Asset path must be strictly confined under 'assets' directory: {asset}")
    return asset


def _parse_step(data: Mapping[str, Any], root: Path) -> TourStep:
    forbidden = _FORBIDDEN_STEP_KEYS.intersection(data)
    if forbidden:
        raise ValueError(f"Step contains forbidden executable fields: {sorted(forbidden)}")
    unknown = set(data) - _ALLOWED_STEP_KEYS
    if unknown:
        raise ValueError(f"Unknown step keys rejected: {sorted(unknown)}")
    step_id = data.get("step_id")
    if not step_id:
        raise ValueError("step_id is required")
    step_type = TourStepType(data["type"])
    if step_type is TourStepType.ACTION and not data.get("anchor"):
        raise ValueError("ACTION step requires an anchor; valid anchor required")
    if step_type is TourStepType.ACTION and "interaction" not in data:
        raise ValueError("ACTION step requires an interaction")
    if step_type is TourStepType.INFO and "interaction" in data:
        raise ValueError("INFO steps cannot contain interaction definitions")
    if step_type is TourStepType.DEMO and not data.get("demo"):
        raise ValueError("DEMO step requires a demo definition")
    interaction_data, demo_data = data.get("interaction"), data.get("demo")
    if interaction_data is not None and (not isinstance(interaction_data, Mapping) or set(interaction_data) - _ALLOWED_INTERACTION_KEYS):
        raise ValueError("Unknown keys in interaction object")
    if demo_data is not None and (not isinstance(demo_data, Mapping) or set(demo_data) - _ALLOWED_DEMO_KEYS):
        raise ValueError("Unknown keys in demo object")
    surface_data = data.get("surface")
    if surface_data is not None and (not isinstance(surface_data, Mapping) or set(surface_data) - _ALLOWED_SURFACE_KEYS):
        raise ValueError("Unknown keys in surface object")
    safety_data = data.get("safety", {})
    if not isinstance(safety_data, Mapping) or set(safety_data) - _ALLOWED_SAFETY_KEYS:
        raise ValueError("Unknown keys in safety object")
    step_preconditions = tuple(Precondition(value) for value in data.get("preconditions", ()))
    demo = None if demo_data is None else DemoSpec(_validate_asset_path(demo_data.get("asset", ""), root), demo_data.get("media_type", "IMAGE"), demo_data.get("fit", "contain"))
    return TourStep(
        step_id=step_id, step_type=step_type, callout=_parse_callout(data.get("callout", {})),
        safety=_parse_safety(safety_data, step_type), surface=_parse_surface(surface_data),
        anchor=data.get("anchor"), target_policy=TargetPolicy(data.get("target_policy", "FALLBACK_TO_INFO")),
        interaction=None if interaction_data is None else InteractionSpec(InteractionKind(interaction_data.get("kind", ""))), demo=demo,
        preconditions=step_preconditions,
    )


def parse_tour_definition(payload: Mapping[str, object], tutorial_root: Optional[Path] = None) -> TourDefinition:
    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"Unsupported schema_version: {schema_version}")
    unknown = set(payload) - _ALLOWED_ROOT_KEYS
    if unknown:
        raise ValueError(f"Unknown root keys rejected: {sorted(unknown)}")
    steps_data = payload.get("steps", [])
    if not steps_data:
        raise ValueError("Steps cannot be empty")
    root = (Path.cwd() if tutorial_root is None else Path(tutorial_root)).resolve()
    guide_preconditions = tuple(Precondition(value) for value in payload.get("preconditions", ()))
    seen, steps = set(), []
    for step_data in steps_data:
        step = _parse_step(step_data, root)
        if step.step_id in seen:
            raise ValueError(f"Duplicate step_id detected: {step.step_id}")
        seen.add(step.step_id)
        steps.append(step)
    return TourDefinition(
        schema_version=schema_version, guide_id=payload.get("guide_id", ""), content_version=payload.get("content_version", 1),
        title=payload.get("title", ""), description=payload.get("description", ""), category=payload.get("category", ""),
        estimated_minutes=payload.get("estimated_minutes", 0), steps=tuple(steps), preconditions=guide_preconditions,
    )


class TourParser:
    @staticmethod
    def parse_guide(data: Mapping[str, object], tutorial_root: Optional[Path] = None) -> TourDefinition:
        return parse_tour_definition(data, tutorial_root)


class TourCatalog:
    def __init__(self, tutorial_root: Path):
        self.tutorial_root = Path(tutorial_root).resolve()
        self._guides: dict[str, TourDefinition] = {}
        self._errors: list[str] = []

    @property
    def errors(self) -> list[str]:
        return self._errors

    def load_guide(self, relative_path: str) -> TourDefinition:
        candidate = (self.tutorial_root / relative_path).resolve()
        if candidate != self.tutorial_root and self.tutorial_root not in candidate.parents:
            raise ValueError(f"Guide path traversal detected: {relative_path}")
        if not candidate.exists():
            raise FileNotFoundError(f"Guide file not found: {candidate}")
        with candidate.open("r", encoding="utf-8") as handle:
            return TourParser.parse_guide(json.load(handle), self.tutorial_root)

    def load_all(self) -> tuple[TourDefinition, ...]:
        self._guides.clear(); self._errors.clear()
        catalog_path = self.tutorial_root / "catalog.json"
        if not catalog_path.exists():
            self._errors.append("catalog.json not found")
            return ()
        try:
            with catalog_path.open("r", encoding="utf-8") as handle:
                catalog_data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            self._errors.append(f"Failed to parse catalog.json: {exc}")
            return ()
        for relative_path in catalog_data.get("guides", []):
            try:
                guide = self.load_guide(relative_path)
                if guide.guide_id in self._guides:
                    self._errors.append(f"Duplicate guide_id '{guide.guide_id}' in {relative_path}")
                    continue
                self._guides[guide.guide_id] = guide
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                message = f"Failed to load guide '{relative_path}': {exc}"
                self._errors.append(message)
                logger.error("[TOUR] Catalog load failed: %s", message)
        return tuple(self._guides.values())

    def get_guide(self, guide_id: str) -> Optional[TourDefinition]:
        return self._guides.get(guide_id)
