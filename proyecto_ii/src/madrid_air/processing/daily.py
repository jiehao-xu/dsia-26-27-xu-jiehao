"""Medias diarias de NO2: una fila por fecha local, incluidos los días sin datos."""
import numpy as np
import pandas as pd

from madrid_air.config import TZ


def daily_no2(hourly, start, as_of):
    """Exige al menos el 75 % de horas válidas; nunca rellena el objetivo.

    Un día de cambio horario puede tener 23 o 25 horas. El día actual queda
    excluido aunque ya contenga alguna observación, pues todavía no ha terminado.
    """
    first_day = pd.Timestamp(start).normalize()
    last_day = min(pd.Timestamp(as_of).normalize(),
                   pd.Timestamp.now(tz=TZ).tz_localize(None).normalize() - pd.Timedelta(days=1))
    if first_day > last_day:
        raise ValueError("No hay días completos en el intervalo solicitado.")
    data = hourly.copy()
    data["date"] = data.timestamp.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    data = data.drop_duplicates("timestamp", keep="last")
    data["no2"] = pd.to_numeric(data.no2, errors="coerce").where(lambda values: values >= 0)
    grouped = data.groupby("date").agg(no2=("no2", "mean"), valid_hours=("no2", "count"))
    daily = grouped.reindex(pd.date_range(first_day, last_day, freq="D", name="date"))
    daily["valid_hours"] = daily.valid_hours.fillna(0).astype(int)
    # Localizamos ambos extremos por separado: un día local no siempre dura 24 h.
    midnight = daily.index.tz_localize(TZ).tz_convert("UTC")
    next_midnight = (daily.index + pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC")
    daily["expected_hours"] = (next_midnight - midnight) / pd.Timedelta(hours=1)
    daily["coverage"] = daily.valid_hours / daily.expected_hours
    enough_hours = daily.valid_hours >= np.ceil(daily.expected_hours * 0.75)
    daily["no2"] = daily.no2.where(enough_hours)
    return daily
