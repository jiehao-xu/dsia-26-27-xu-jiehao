import numpy as np
import pandas as pd

from madrid_air.config import TZ

FEATURES = ["no2", "no2_lag_1", "no2_lag_24", "no2_mean_24", "traffic_intensity",
            "traffic_occupation", "traffic_sensor_count", "weather_temperature", "weather_humidity",
            "weather_wind_speed", "weather_precipitation", "weather_temperature_min",
            "weather_temperature_max", "hour_sin", "hour_cos", "weekday", "month",
            "is_holiday", "is_workday"]
TARGET = "target_no2"


def add_features(frame):
    """Añade predictores y el objetivo de la siguiente hora a la tabla integrada.

    La entrada debe tener una fila por hora, incluidos los huecos. Devuelve una
    copia: no modifica el DataFrame recibido. Solo target_no2 mira hacia delante;
    esa columna nunca forma parte de FEATURES, la lista que recibe el modelo.
    """
    frame = frame.sort_values("timestamp").reset_index(drop=True).copy()
    has_duplicate_hours = frame.timestamp.duplicated().any()
    time_between_rows = frame.timestamp.diff().dropna()
    is_hourly = time_between_rows.eq(pd.Timedelta(hours=1)).all()
    if has_duplicate_hours or not is_hourly:
        raise ValueError("Las features requieren una rejilla horaria completa y única.")
    local = frame.timestamp.dt.tz_convert(TZ)
    # Seno y coseno expresan el ciclo diario: las 23:00 están cerca de las 00:00.
    frame["hour_sin"] = np.sin(2 * np.pi * local.dt.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * local.dt.hour / 24)
    frame["weekday"] = local.dt.dayofweek
    frame["month"] = local.dt.month
    # shift(1) trae la fila anterior; shift(24), la de hace 24 horas.
    # rolling(24) incluye la hora actual, ya terminada al emitir la predicción.
    frame["no2_lag_1"] = frame.no2.shift(1)
    frame["no2_lag_24"] = frame.no2.shift(24)
    frame["no2_mean_24"] = frame.no2.rolling(24, min_periods=24).mean()
    # Emisión tras cerrar el intervalo t; objetivo: concentración en t+1.
    frame["target_timestamp"] = frame.timestamp + pd.Timedelta(hours=1)
    frame[TARGET] = frame.no2.shift(-1)
    return frame
