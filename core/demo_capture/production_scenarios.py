from core.demo_capture.models import (
    CaptureProfile,
    CaptureScenario,
    CaptureScope,
    CaptureTarget,
    ClickAction,
    HoldAction,
    OutputFormat,
    OutputSpec,
    WaitSettledAction,
    WaitVisibleAction,
)
from core.demo_capture.registry import DemoScenarioRegistry


def build_production_registry() -> DemoScenarioRegistry:
    return DemoScenarioRegistry(
        (
            CaptureScenario(
                id="getting_started_generation",
                target=CaptureTarget(
                    scope=CaptureScope.FULL_WINDOW,
                    semantic_id=None,
                    padding=0,
                ),
                profile=CaptureProfile(
                    window_size=(960, 540),
                    fps=10,
                    output_scale=1.0,
                    default_wait_timeout_ms=3000,
                ),
                actions=(
                    ClickAction("navigation.video_workspace"),
                    WaitVisibleAction("workspace.ai_generation"),
                    HoldAction(1000),
                    WaitSettledAction(),
                ),
                output=OutputSpec(
                    "getting_started_generation.gif",
                    OutputFormat.GIF,
                ),
            ),
        )
    )
