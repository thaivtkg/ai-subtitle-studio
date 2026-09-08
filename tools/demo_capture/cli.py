import argparse
import sys
import time
from pathlib import Path

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import ExecutionMode
from core.demo_capture.batch import BatchProcessor
from core.demo_capture.frame_clock import FrameClock
from core.demo_capture.runner import capture_to_staging


def _get_registry():
    from core.demo_capture.registry import DemoScenarioRegistry

    return DemoScenarioRegistry([])


def _asset_root() -> Path:
    return Path("resources/tutorials/assets")


class _MainWindowFrameCapture:
    def capture(self, target, main_window):
        from ui.demo_capture.anchor_registry_adapter import AnchorRegistryCaptureAdapter
        from ui.demo_capture.frame_capture import FrameCaptureService

        resolver = AnchorRegistryCaptureAdapter(main_window.tour_anchor_registry)
        return FrameCaptureService(resolver).capture(target, main_window)


def _run_batch(
    registry,
    mode,
    staging_dir,
    writer,
    env_factory,
    normalizer,
    encoder,
    validator,
    frame_capture=None,
):
    def runner_fn(scenario, selected_mode, directory):
        from core.demo_capture.frame_clock import FrameClock

        return capture_to_staging(
            scenario,
            selected_mode,
            directory,
            env_factory,
            FrameClock(scenario.profile.fps, time.monotonic),
            frame_capture,
            normalizer,
            encoder,
            validator,
        )

    return BatchProcessor(registry, staging_dir, writer, runner_fn).run_all(mode)


def main(args=None):
    parser = argparse.ArgumentParser(prog="python -m tools.demo_capture")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("validate")
    generate = subparsers.add_parser("generate")
    target = generate.add_mutually_exclusive_group(required=True)
    target.add_argument("scenario_id", nargs="?", default=None)
    target.add_argument("--all", action="store_true")
    generate.add_argument("--mode", choices=["isolated", "real"], default="isolated")

    parsed = parser.parse_args(args)
    if parsed.command == "generate" and getattr(sys, "frozen", False):
        print("Error: Demo capture is a developer tool and cannot generate in a frozen build.")
        return 4
    if parsed.command == "list":
        registry = _get_registry()
        print(f"Listing {len(registry.ids())} scenarios...")
        return 0
    if parsed.command == "validate":
        try:
            from core.demo_capture.validation import TutorialAssetValidator

            TutorialAssetValidator().validate_registry_assets(
                _get_registry(), _asset_root()
            )
            print("Validation passed.")
            return 0
        except CaptureRunError as error:
            print(f"Validation failed: {error.message}")
            return 3
        except Exception as error:
            print(f"Validation error: {error}")
            return 3
    if parsed.all and parsed.mode == "real":
        print("Error: REAL_APP mode is forbidden for --all batch generation.")
        return 2
    try:
        return _do_generate(parsed)
    except CaptureRunError as error:
        print(f"Error: {error.error_code} - {error.message}")
        if error.error_code == CaptureErrorCode.OUTPUT_VALIDATION_FAILED:
            return 3
        if error.error_code in (
            CaptureErrorCode.REAL_APP_ENVIRONMENT_UNAVAILABLE,
            CaptureErrorCode.REAL_APP_OWNERSHIP_FAILED,
        ):
            return 4
        if error.error_code == CaptureErrorCode.INVALID_SCENARIO:
            return 2
        return 1
    except Exception as error:
        print(f"Unknown error: {error}")
        return 1


def _do_generate(parsed):
    from core.demo_capture.artifact_writer import ArtifactWriter
    from core.demo_capture.frame_clock import FrameClock
    from core.demo_capture.runner import generate_one
    from core.demo_capture.validation import TutorialAssetValidator
    from ui.demo_capture.encoder import PillowAssetEncoder
    from ui.demo_capture.frame_normalizer import FrameNormalizer

    mode = ExecutionMode.ISOLATED if parsed.mode == "isolated" else ExecutionMode.REAL_APP
    registry = _get_registry()
    asset_root = _asset_root()
    staging_dir = asset_root / ".staging"
    writer = ArtifactWriter(asset_root)
    validator = TutorialAssetValidator()
    encoder = PillowAssetEncoder()
    normalizer = FrameNormalizer()

    if mode == ExecutionMode.ISOLATED:
        from ui.demo_capture.isolated_app_factory import IsolatedAppFactory

        env_factory = IsolatedAppFactory()
    else:
        from ui.demo_capture.real_app.real_app_capture_factory import RealAppCaptureFactory

        env_factory = RealAppCaptureFactory()
    frame_capture = _MainWindowFrameCapture()

    if parsed.all:
        results = _run_batch(
            registry,
            mode,
            staging_dir,
            writer,
            env_factory,
            normalizer,
            encoder,
            validator,
            frame_capture,
        )
        return 1 if any(error for _, _, error in results) else 0

    scenario = registry.get(parsed.scenario_id)
    if scenario is None:
        raise CaptureRunError(
            CaptureErrorCode.INVALID_SCENARIO,
            f"Scenario not found: {parsed.scenario_id}",
        )
    generate_one(
        scenario,
        mode,
        staging_dir,
        writer,
        env_factory,
        FrameClock(scenario.profile.fps, time.monotonic),
        frame_capture,
        normalizer,
        encoder,
        validator,
    )
    return 0
