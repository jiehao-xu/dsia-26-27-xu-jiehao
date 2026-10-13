import json
from pathlib import Path
import pandas as pd
from internet_app.errors import DataLoadError, DataSaveError


def load(path: Path) -> pd.DataFrame | dict:
    if not path.is_file():
        raise DataLoadError(f"No existe el fichero: {path}")

    extension = path.suffix.lower()

    if extension == ".csv":
        return pd.read_csv(path, dtype="string")

    if extension == ".tab":
        return pd.read_csv(path, sep="\t", dtype="string")

    if extension == ".json":
        try:
            diccionario = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise DataLoadError(f"No se puede leer el JSON: {path}") from error
        if not isinstance(diccionario, dict):
            raise DataLoadError("El JSON debe contener un objeto")
        return diccionario

    raise DataLoadError(f"Extensión no soportada: {extension}")


    
def save(df: pd.DataFrame, path: Path) -> None:
    """
    File saver
    """
    if not path.parent.is_dir():
        raise DataSaveError(f"No existe la carpeta: {path.parent}")
    df.to_csv(path, index=False)

