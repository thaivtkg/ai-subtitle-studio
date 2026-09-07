from typing import Dict, Iterable, Optional, Tuple

from core.demo_capture.models import CaptureScenario


class DemoScenarioRegistry:
    def __init__(self, scenarios: Iterable[CaptureScenario]) -> None:
        self._scenarios: Tuple[CaptureScenario, ...] = tuple(scenarios)
        self._by_id: Dict[str, CaptureScenario] = {}
        seen_outputs = set()

        for scenario in self._scenarios:
            if scenario.id in self._by_id:
                raise ValueError(f"Duplicate scenario ID: {scenario.id}")
            if scenario.output.filename in seen_outputs:
                raise ValueError(f"Duplicate output filename: {scenario.output.filename}")

            self._by_id[scenario.id] = scenario
            seen_outputs.add(scenario.output.filename)

    def get(self, scenario_id: str) -> Optional[CaptureScenario]:
        return self._by_id.get(scenario_id)

    def all(self) -> Tuple[CaptureScenario, ...]:
        return self._scenarios

    def ids(self) -> Tuple[str, ...]:
        return tuple(self._by_id.keys())
