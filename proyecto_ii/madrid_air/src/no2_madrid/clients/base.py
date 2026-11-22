from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PredictionContext:
    date: str
    scope: str
    no2: float
    missing_features: int
    test_mae: float
    network_stations: int = 0


class ExplanationClient(Protocol):
    def explain(self, context: PredictionContext) -> str: ...
