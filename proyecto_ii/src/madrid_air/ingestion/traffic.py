import numpy as np
import pandas as pd

from madrid_air.ingestion.common import download, municipal_files, period, resources
from madrid_air.processing.common import csv_chunks
from madrid_air.storage import write_csv


def select_sensors(client, settings):
    """Devuelve IDs explícitos o los sensores dentro del radio de Escuelas Aguirre.

    La selección automática usa un inventario anterior al inicio del estudio.
    Guarda traffic_sensors.csv para poder revisar qué sensores se han elegido.
    """
    if settings.sensor_ids:
        return settings.sensor_ids
    items = [r for r in resources(client, "202468-0-intensidad-trafico")
             if r.get("format", "").upper() == "CSV"]
    start, _ = settings.bounds
    eligible = [(period(r)[0], r) for r in items if period(r)[0] <= start]
    if not eligible:
        raise ValueError("No hay inventario anterior al inicio; indica TRAFFIC_SENSOR_IDS.")
    _, resource = max(eligible, key=lambda item: item[0])
    path = download(client, resource["url"], settings.root / "data/raw/traffic", resource["id"], ".csv")
    frame = pd.concat(csv_chunks(path), ignore_index=True)
    lat = np.radians(pd.to_numeric(frame["latitud"], errors="coerce"))
    lon = np.radians(pd.to_numeric(frame["longitud"], errors="coerce"))
    lat0, lon0 = np.radians([40.42156, -3.68232])
    # Fórmula de Haversine: distancia sobre una esfera a partir de latitud y
    # longitud en radianes. 6 371 000 es el radio aproximado terrestre en metros.
    a = np.sin((lat-lat0)/2)**2 + np.cos(lat)*np.cos(lat0)*np.sin((lon-lon0)/2)**2
    frame["distance_m"] = 6371000 * 2 * np.arcsin(np.sqrt(a.clip(0, 1)))
    selected = frame.loc[frame.distance_m <= settings.radius_m].sort_values("distance_m")
    if selected.empty:
        raise ValueError("No hay sensores en el radio configurado.")
    write_csv(selected, settings.root / "data/processed/traffic_sensors.csv")
    return tuple(selected["id"].astype(int))


def fetch(client, settings):
    return municipal_files(client, settings, "208627-0-transporte-ptomedida-historico", "traffic")
