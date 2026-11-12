import pandas as pd

from madrid_air.config import TZ


def join_sources(no2, weather, traffic, calendar, start, end, weather_lag_days=7):
    """Combina cuatro DataFrames en una tabla con una fila por hora UTC.

    NO2 y tráfico se unen por hora; calendario y meteorología, por fecha local.
    Un LEFT JOIN conserva todas las horas aunque una fuente no tenga datos.
    validate comprueba la cardinalidad para evitar multiplicar filas por error.
    """
    start_utc = pd.Timestamp(start).tz_localize(TZ).tz_convert("UTC")
    day_after_end = pd.Timestamp(end) + pd.Timedelta(days=1)
    end_utc = day_after_end.tz_localize(TZ).tz_convert("UTC")
    hours = pd.date_range(start_utc, end_utc, freq="h", inclusive="left")
    result = pd.DataFrame({"timestamp": hours})
    result = result.merge(no2, on="timestamp", how="left", validate="one_to_one")
    hourly = traffic.groupby("timestamp", as_index=False).agg(
        traffic_intensity=("intensity", "mean"), traffic_occupation=("occupation", "mean"),
        traffic_sensor_count=("intensity", "count"))
    result = result.merge(hourly, on="timestamp", how="left", validate="one_to_one")
    local = result.timestamp.dt.tz_convert(TZ)
    result["date"] = local.dt.strftime("%Y-%m-%d")
    result = result.merge(calendar, on="date", how="left", validate="many_to_one")
    if result[["is_holiday", "is_workday"]].isna().any().any():
        raise ValueError("El calendario no cubre todas las fechas solicitadas.")
    # Restamos días de calendario local, no bloques de 24 horas UTC: pueden
    # diferir cuando cambia la hora. No usamos el resumen del día en curso.
    local_dates = local.dt.tz_localize(None).dt.normalize()
    weather_dates = local_dates - pd.Timedelta(days=weather_lag_days)
    result["weather_date"] = weather_dates.dt.strftime("%Y-%m-%d")

    weather_columns = {"date": "weather_date"}
    for column in weather.columns:
        if column != "date":
            weather_columns[column] = f"weather_{column}"
    weather = weather.rename(columns=weather_columns)
    return result.merge(weather, on="weather_date", how="left", validate="many_to_one")
