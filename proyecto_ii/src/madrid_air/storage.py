from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

import pandas as pd


@contextmanager
def atomic_path(destination: Path):
    """Proporciona un temporal y sustituye el destino solo si el bloque termina.

    Se usa con ``with atomic_path(destino) as temporal: ...``. El código anterior
    a ``yield`` crea el temporal; el posterior se ejecuta al salir del bloque.
    Si la escritura lanza una excepción, no se ejecuta os.replace: el archivo
    anterior permanece intacto. ``finally`` retira el temporal en ambos casos.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_csv(frame, path):
    """Guarda un DataFrame sin índice de Pandas y con sustitución atómica."""
    with atomic_path(Path(path)) as temporary:
        frame.to_csv(temporary, index=False)


def read_csv(path):
    """Lee un CSV procesado y restaura sus columnas horarias como fechas UTC."""
    frame = pd.read_csv(path)
    for col in ("timestamp", "target_timestamp"):
        if col in frame:
            frame[col] = pd.to_datetime(frame[col], utc=True)
    return frame


def upsert(frame, path, keys):
    """Añade filas nuevas y reemplaza las existentes con la misma clave.

    Ejemplo: si ya hay NO2 para las 10:00 y llega una corrección de esa hora,
    queda la corrección. El orden importa: los datos nuevos se concatenan al
    final y keep='last' conserva la última fila, incluso si contiene ausentes.
    """
    if Path(path).exists():
        frame = pd.concat([read_csv(path), frame], ignore_index=True)
    if frame[keys].isna().any().any():
        raise ValueError(f"Claves vacías en {path}")
    frame = frame.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
    write_csv(frame, path)
    return frame
