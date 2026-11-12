from dataclasses import dataclass
from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv

TZ = "Europe/Madrid"


@dataclass(frozen=True)
class Settings:
    """Configuración compartida: rutas, intervalo de fechas y fuentes de datos.

    Una dataclass agrupa valores relacionados sin escribir un constructor manual.
    frozen=True impide cambiarlos accidentalmente a mitad de una ejecución.
    """
    root: Path
    start: str = "2023-01-01"
    end: str | None = None
    overlap_days: int = 14
    aemet_station: str = "3195"
    aemet_key: str = ""
    sensor_ids: tuple[int, ...] = ()
    radius_m: float = 500
    aemet_lag_days: int = 7

    @classmethod
    def from_env(cls, root: Path, **kwargs):
        """Lee .env; kwargs contiene las opciones elegidas en la línea de comandos."""
        root = root.resolve()
        load_dotenv(root / ".env")
        sensor_ids = []
        for sensor_text in os.getenv("TRAFFIC_SENSOR_IDS", "").split(","):
            if sensor_text.strip():
                sensor_ids.append(int(sensor_text))

        return cls(
            root=root,
            aemet_key=os.getenv("AEMET_API_KEY", ""),
            aemet_station=os.getenv("AEMET_STATION", "3195"),
            sensor_ids=tuple(sensor_ids),
            radius_m=float(os.getenv("TRAFFIC_RADIUS_METERS", "500")),
            aemet_lag_days=int(os.getenv("AEMET_LAG_DAYS", "7")),
            **kwargs,
        )

    @property
    def bounds(self):
        """Devuelve inicio y fin como fechas sin hora, tras validar la configuración."""
        start = pd.Timestamp(self.start).normalize()
        end = pd.Timestamp(self.end or pd.Timestamp.now(tz=TZ).date()).normalize()
        if start > end or self.overlap_days < 1 or self.aemet_lag_days < 1 or self.radius_m <= 0:
            raise ValueError("Revisa fechas, ventana de actualización, radio y retraso de AEMET.")
        return start, end

    def prepare(self):
        """Valida las opciones y crea las carpetas que necesita el pipeline."""
        self.bounds
        for folder in ["raw/no2", "raw/aemet", "raw/traffic", "raw/calendar", "processed", "final"]:
            (self.root / "data" / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "models").mkdir(exist_ok=True)
