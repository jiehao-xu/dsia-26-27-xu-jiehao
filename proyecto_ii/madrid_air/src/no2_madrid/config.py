"""Configuración explícita: las credenciales nunca se serializan."""
from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    output_dir: Path = Path(".")
    min_station_coverage: float = 0.75
    meteo_lag_days: int = 7
    no2_lag_days: int = 1
    traffic_lag_days: int = 1
    use_traffic: bool = True
    ai_mode: str = "mock"
    ai_provider: str = "google"
    google_model: str = "gemini-3.1-flash-lite"
    google_api_key: str = field(default="", repr=False)
    random_state: int = 42

    def __post_init__(self):
        if self.ai_mode not in {"mock", "real"} or self.ai_provider != "google":
            raise ValueError("AI_MODE debe ser mock/real y AI_PROVIDER google.")
        if min(self.meteo_lag_days, self.no2_lag_days, self.traffic_lag_days) < 1:
            raise ValueError("Los retrasos deben ser >= 1 día.")
        if not 0 < self.min_station_coverage <= 1:
            raise ValueError("MIN_STATION_COVERAGE debe estar entre 0 y 1.")

    @property
    def process_dir(self):
        return self.data_dir / "process"

    @property
    def dataset_path(self):
        return self.data_dir / "dataset" / "daily.csv"

    @property
    def model_path(self):
        return self.output_dir / "artifacts" / "model.joblib"

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            output_dir=Path(os.getenv("OUTPUT_DIR", ".")),
            min_station_coverage=float(os.getenv("MIN_STATION_COVERAGE", "0.75")),
            meteo_lag_days=int(os.getenv("METEO_LAG_DAYS", "7")),
            no2_lag_days=int(os.getenv("NO2_LAG_DAYS", "1")),
            traffic_lag_days=int(os.getenv("TRAFFIC_LAG_DAYS", "1")),
            use_traffic=os.getenv("USE_TRAFFIC", "true").lower() in {"1", "true", "yes"},
            ai_mode=os.getenv("AI_MODE", "mock"),
            ai_provider=os.getenv("AI_PROVIDER", "google"),
            google_model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite"),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            random_state=int(os.getenv("RANDOM_STATE", "42")),
        )
