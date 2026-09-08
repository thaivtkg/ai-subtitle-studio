from pathlib import Path

from core.demo_capture.errors import CaptureErrorCode, CaptureRunError
from core.demo_capture.models import ExecutionMode


class BatchProcessor:
    def __init__(self, registry, staging_dir: Path, writer, runner_fn):
        self.registry = registry
        self.staging_dir = Path(staging_dir)
        self.writer = writer
        self.runner_fn = runner_fn

    def run_all(self, mode: ExecutionMode):
        if mode == ExecutionMode.REAL_APP:
            raise CaptureRunError(
                CaptureErrorCode.INVALID_SCENARIO,
                "REAL_APP forbidden for --all",
            )

        results = []
        for scenario in self.registry.all():
            try:
                staged_path = self.runner_fn(scenario, mode, self.staging_dir)
                results.append((scenario, staged_path, None))
            except Exception as error:
                staged_path = self.staging_dir / scenario.output.filename
                results.append((scenario, staged_path if staged_path.is_file() else None, error))

        if any(error is not None for _, _, error in results):
            for _, staged_path, _ in results:
                if staged_path is not None and Path(staged_path).is_file():
                    try:
                        Path(staged_path).unlink()
                    except OSError:
                        pass
            return results
        for scenario, staged_path, _ in results:
            self.writer.commit(staged_path, scenario.output)
        return results
