"""Variables causales respecto a la fecha objetivo, en días de calendario."""
import numpy as np
import pandas as pd

from no2_madrid.config import Settings


def make_features(daily: pd.DataFrame, settings: Settings):
    if daily.index.has_duplicates or not isinstance(daily.index, pd.DatetimeIndex):
        raise ValueError("El dataset necesita un DatetimeIndex único.")
    daily = daily.sort_index().reindex(pd.date_range(daily.index.min(), daily.index.max(), name="FECHA"))
    x = pd.DataFrame(index=daily.index)
    lag = settings.no2_lag_days
    for offset in (0, 1, 6):
        x[f"no2_lag_{lag+offset}"] = daily.NO2.shift(lag+offset)
    prior = daily.NO2.shift(lag)
    x["no2_mean_7"] = prior.rolling(7, min_periods=3).mean()
    x["no2_std_7"] = prior.rolling(7, min_periods=3).std()
    for column in daily.filter(regex="^(METEO_|TRAFICO_)"):
        delay = settings.meteo_lag_days if column.startswith("METEO_") else settings.traffic_lag_days
        x[f"{column}_lag_{delay}"] = daily[column].shift(delay)
    x["weekday"] = x.index.day_of_week
    x["month_sin"] = np.sin(2*np.pi*x.index.month/12)
    x["month_cos"] = np.cos(2*np.pi*x.index.month/12)
    x["weekend"] = (x.index.day_of_week >= 5).astype(int)
    # Festivos ausentes no se convierten silenciosamente en laborables.
    x["holiday"] = daily.TIPO_DIA.map({"festivo": 1, "laborable": 0, "sabado": 0, "domingo": 0})
    x["calendar_missing"] = daily.TIPO_DIA.isna().astype(int)
    return x.replace([np.inf, -np.inf], np.nan)
