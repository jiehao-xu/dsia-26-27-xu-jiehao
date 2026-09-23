import os
from pathlib import Path
import pandas as pd
from error import DataLoadError, DataSaveError


class CsvSalesRepository:
    def load(self, path: Path) -> pd.DataFrame:
        """
        File loader
        """
        if not path.exists():
            raise DataLoadError(f"No existe el fichero: {path}")
        return pd.read_csv(path)
        
    def save(self, df: pd.DataFrame, path: Path) -> None:
        if not path.exists():
            raise DataSaveError(f"No existe la ruta: {path}")
        os.makedirs(path.parent, exist_ok=True)
        df.to_csv(path, index=False)

