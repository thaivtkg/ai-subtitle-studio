from pathlib import Path
from typing import Any, Protocol, Tuple

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import CaptureScenario, ExecutionMode, OutputFormat


class CaptureEnvironmentPort(Protocol):
    def __enter__(self) -> Tuple[Any, Any, Any]: ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...


def capture_to_staging(
    scenario: CaptureScenario,
    mode: ExecutionMode,
    staging_dir: Path,
    env_factory: Any,
    clock: Any,
    frame_capture: Any,
    normalizer: Any,
    encoder: Any,
    validator: Any,
) -> Path:
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / scenario.output.filename
    frames = []

    try:
        with env_factory(scenario, mode) as (main_window, action_driver, _):
            clock.start()
            frames.append(frame_capture.capture(scenario.target, main_window))

            def tick() -> None:
                for _ in range(clock.due_count()):
                    frames.append(frame_capture.capture(scenario.target, main_window))

            for index, action in enumerate(scenario.actions):
                try:
                    action_driver.execute(action, scenario.profile, tick)
                except CaptureRunError as error:
                    error.scenario_id = scenario.id
                    error.action_index = index
                    error.action_kind = type(action).__name__
                    if hasattr(action, "target"):
                        error.target = action.target
                    raise
                except Exception as error:
                    raise CaptureRunError(
                        CaptureErrorCode.ACTION_FAILED,
                        str(error),
                        scenario_id=scenario.id,
                        action_index=index,
                        action_kind=type(action).__name__,
                    ) from error

            frames.append(frame_capture.capture(scenario.target, main_window))
            normalized = normalizer.normalize(frames, scenario.profile.output_scale)
            if scenario.output.format == OutputFormat.GIF:
                encoder.encode_gif(normalized, staging_path, scenario.profile.fps)
            else:
                encoder.encode_png(normalized[-1], staging_path)
            validator.validate_file(staging_path, scenario.output)
    except CaptureRunError:
        raise
    except Exception as error:
        raise CaptureRunError(
            CaptureErrorCode.CLEANUP_FAILED,
            f"Capture environment failed: {error}",
            scenario_id=scenario.id,
        ) from error

    return staging_path


def generate_one(
    scenario: CaptureScenario,
    mode: ExecutionMode,
    staging_dir: Path,
    writer: Any,
    env_factory: Any,
    clock: Any,
    frame_capture: Any,
    normalizer: Any,
    encoder: Any,
    validator: Any,
) -> Path:
    staged_path = capture_to_staging(
        scenario,
        mode,
        staging_dir,
        env_factory,
        clock,
        frame_capture,
        normalizer,
        encoder,
        validator,
    )
    return writer.commit(staged_path, scenario.output)
