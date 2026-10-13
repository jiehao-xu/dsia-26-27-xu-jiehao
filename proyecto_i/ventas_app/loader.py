import os
from pathlib import Path
import pandas as pd
from ventas_app.errors import DataLoadError, DataSaveError


class CsvSalesRepository:
    def load(self, path: Path) -> pd.DataFrame:
        """
        File loader
        """
        if not path.exists():
            raise DataLoadError(f"No existe el fichero: {path}")
        return pd.read_csv(path)
        
    def save(self, df: pd.DataFrame, path: Path) -> None:
        """
        File saver
        """
        if not path.parent.is_dir():
            raise DataSaveError(f"No existe la carpeta: {path.parent}")
        df.to_csv(path, index=False)

