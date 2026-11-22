"""Rutas y escritura segura de los datos limpios; nunca modifica raw."""

import json
import os
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESS_DIR = DATA_DIR / "process"
VERSION = 1


def firma(origen):
    estado = origen.stat()
    return {"version": VERSION, "origen": str(origen.resolve()),
            "bytes": estado.st_size, "mtime_ns": estado.st_mtime_ns}


def informe_path(destino):
    return destino.with_name(destino.name + ".json")


def esta_actualizado(origen, destino):
    informe = informe_path(destino)
    if not destino.is_file() or not informe.is_file():
        return False
    return json.loads(informe.read_text(encoding="utf-8")).get("fuente") == firma(origen)


def guardar_informe(origen, destino, **metricas):
    informe_path(destino).write_text(
        json.dumps({"fuente": firma(origen), **metricas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def guardar_csv(datos, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    try:
        datos.to_csv(temporal, sep=";", index=False, date_format="%Y-%m-%d")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)


def fechas(datos, columna_dia="DIA"):
    return pd.to_datetime(
        {"year": datos["ANO"], "month": datos["MES"], "day": datos[columna_dia]},
        errors="coerce",
    )


def comprobar_claves(datos, claves):
    if datos.duplicated(claves).any():
        raise ValueError(f"Hay registros distintos con la misma clave: {claves}")
