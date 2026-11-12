import pandas as pd

from madrid_air.processing.common import csv_chunks, numeric, to_utc


def clean(path):
    """Convierte el CSV ancho H01–H24 en timestamp UTC + no2 de Escuelas Aguirre.

    Cada fila original describe un día de una estación y un contaminante.
    Tras filtrar la estación 8 y la magnitud 8 (NO2), producimos una fila por
    hora. La columna V correspondiente indica si la medida es válida.
    """
    parts = []
    for frame in csv_chunks(path):
        frame = frame.loc[(numeric(frame.estacion) == 8) & (numeric(frame.magnitud) == 8)
                          & (numeric(frame.provincia) == 28) & (numeric(frame.municipio) == 79)].copy()
        if frame.empty:
            continue
        day = pd.to_datetime(frame[["ano", "mes", "dia"]].rename(
            columns={"ano": "year", "mes": "month", "dia": "day"}), errors="raise")
        for hour in range(1, 25):
            values = numeric(frame[f"h{hour:02}"])
            values = values.where(frame[f"v{hour:02}"].str.strip().eq("V") & values.ge(0))
            # Etiqueta al inicio del intervalo: H24 representa 23:00–24:00.
            parts.append(pd.DataFrame({"timestamp": to_utc(day + pd.Timedelta(hours=hour-1)),
                                       "no2": values}))
    if not parts:
        raise ValueError(f"Sin NO2 de Escuelas Aguirre en {path}")
    return pd.concat(parts).dropna(subset=["timestamp"]).drop_duplicates("timestamp", keep="last")
