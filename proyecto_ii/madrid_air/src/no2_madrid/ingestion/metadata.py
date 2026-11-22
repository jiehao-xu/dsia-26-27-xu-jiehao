"""Catálogos normalizados WGS84 para selección de tráfico por distancia."""
import re
import unicodedata

import pandas as pd

from no2_madrid.config import Settings
from no2_madrid.ingestion.portal import latest_csv
from no2_madrid.io import write_json
from no2_madrid.preprocess.common import guardar_csv


def normalize(frame, kind):
    def key(value):
        value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]", "", value)
    columns = {key(c): c for c in frame}
    def find(*options):
        for option in options:
            if option in columns:
                return columns[option]
        raise ValueError(f"Catálogo sin columnas esperadas {options}; columnas: {list(frame)}")
    id_col = find("id", "idsensor") if kind == "traffic" else find("codigo", "codigocorto", "estacion", "codigoestacion")
    result = pd.DataFrame()
    result["ID_SENSOR" if kind == "traffic" else "ESTACION"] = pd.to_numeric(frame[id_col], errors="raise").astype(int)
    if kind == "air":
        # Algunos catálogos usan el código completo 28079004.
        result["ESTACION"] %= 1000
    for target, alternatives in [("LATITUD", ("latitud", "latitudwgs84", "latitude")),
                                  ("LONGITUD", ("longitud", "longitudwgs84", "longitude"))]:
        result[target] = pd.to_numeric(frame[find(*alternatives)].astype(str).str.replace(",", "."), errors="coerce")
    result = result.dropna().drop_duplicates()
    if result.iloc[:, 0].duplicated().any():
        raise ValueError("El catálogo tiene ubicaciones contradictorias para un identificador.")
    return result


def ingest_metadata(settings: Settings):
    sources = {}
    for kind, dataset, filename in [("air", "212629-0-estaciones-control-aire", "air_stations.csv"),
                                    ("traffic", "202468-0-intensidad-trafico", "traffic_sensors.csv")]:
        frame, source = latest_csv(dataset)
        guardar_csv(normalize(frame, kind), settings.data_dir / "metadata" / filename)
        sources[kind] = source
    write_json(settings.data_dir / "metadata" / "sources.json", sources)
