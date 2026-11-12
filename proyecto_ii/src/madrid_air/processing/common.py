"""Lectura de originales y conversiones compartidas por los limpiadores."""
import io
from pathlib import Path
import zipfile

import pandas as pd

from madrid_air.config import TZ


def csv_chunks(path, chunksize=100_000):
    """Entrega bloques de filas de un CSV o de los CSV contenidos en un ZIP.

    Leer por bloques evita cargar todo el tráfico de Madrid en memoria.
    ``yield from`` entrega, uno por uno, los bloques que produce otra función.
    """
    if Path(path).suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            csv_names = []
            for name in archive.namelist():
                if name.lower().endswith(".csv"):
                    csv_names.append(name)
            if not csv_names:
                raise ValueError(f"ZIP sin CSV: {path}")
            for name in sorted(csv_names):
                with archive.open(name) as source:
                    yield from read_chunks(source, chunksize)
    else:
        with open(path, "rb") as source:
            yield from read_chunks(source, chunksize)


def read_chunks(source, chunksize):
    """Lee un archivo binario abierto y normaliza los nombres de sus columnas."""
    sample = source.read(65536)
    source.seek(0)  # Volvemos al principio después de comprobar la codificación.
    try:
        sample.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        encoding = "cp1252"

    text_file = io.TextIOWrapper(source, encoding=encoding)
    with pd.read_csv(text_file, sep=";", dtype=str, chunksize=chunksize) as reader:
        for data in reader:
            data.columns = data.columns.str.strip().str.lower()
            yield data


def numeric(series):
    """Convierte '12,5' en 12.5; un valor no numérico pasa a ser ausente."""
    text_values = series.astype("string").str.strip()
    decimal_values = text_values.str.replace(",", ".", regex=False)
    return pd.to_numeric(decimal_values, errors="coerce")


def to_utc(local):
    """Interpreta horas locales de Madrid y las convierte a UTC."""
    # El formato municipal no identifica el pliegue DST: se omiten horas ambiguas.
    return local.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
