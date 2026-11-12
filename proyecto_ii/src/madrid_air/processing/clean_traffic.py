import pandas as pd

from madrid_air.processing.common import csv_chunks, numeric, to_utc


def clean(path, sensor_ids):
    """Filtra sensores y devuelve medias horarias por timestamp + sensor_id.

    Primero se eliminan duplicados de la medida original, luego se agrupa por
    hora. Se conservan los valores inválidos como ausentes, no como tráfico cero.
    """
    parts = []
    for frame in csv_chunks(path):
        frame = frame.rename(columns={"idelem": "id"})
        frame = frame.loc[numeric(frame["id"]).isin(sensor_ids)].copy()
        if frame.empty:
            continue
        good = frame.error.str.strip().eq("N") & numeric(frame.periodo_integracion).gt(0)
        parts.append(pd.DataFrame({
            "timestamp": to_utc(pd.to_datetime(frame.fecha)),
            "sensor_id": numeric(frame.id).astype(int),
            "intensity": numeric(frame.intensidad).where(good & numeric(frame.intensidad).ge(0)),
            "occupation": numeric(frame.ocupacion).where(good & numeric(frame.ocupacion).between(0, 100)),
        }))
    if not parts:
        return pd.DataFrame(columns=["timestamp", "sensor_id", "intensity", "occupation"])
    frame = pd.concat(parts).dropna(subset=["timestamp"])
    frame = frame.drop_duplicates(["timestamp", "sensor_id"], keep="last")
    frame["timestamp"] = frame.timestamp.dt.floor("h")
    # Intensidad ya está en vehículos/hora; se promedia, no se suman cuatro tasas.
    return frame.groupby(["timestamp", "sensor_id"], as_index=False)[["intensity", "occupation"]].mean()
