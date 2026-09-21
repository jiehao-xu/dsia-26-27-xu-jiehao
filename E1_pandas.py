import os
from pathlib import Path
import pandas as pd
import numpy as np
import json


def read_csv(path:str, file:str) -> pd.DataFrame:
    csv_path = os.path.join(path, file)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"File {file} not found in path {path}")
    csv = pd.read_csv(csv_path)
    return csv

def save_clean_csv(df: pd.DataFrame, path: str, file: str) -> None:
    csv_path = os.path.join(path, file)

    os.makedirs(path, exist_ok=True)

    df.to_csv(csv_path, index=False)

def save_quality_json(
    work: pd.DataFrame,
    validos: pd.DataFrame,
    errores: pd.DataFrame,
    path: str,
    file: str
) -> None:

    json_path = os.path.join(path, file)

    os.makedirs(path, exist_ok=True)

    datos = {
        "filas_totales": len(work),
        "filas_validas": len(validos),
        "filas_invalidas": len(errores),
        "importe_total": validos["importe"].sum()
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4)

def validar_ventas(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Reglas mínimas:
        unidades numérica y > 0
        precio_unitario numérico y > 0
        columnas derivadas: importe = unidades * precio_unitario solo en válidos
    Devuelve (validos, errores)
    """
    work = frame.copy()
    work["unidades"] = pd.to_numeric(work["unidades"], errors="coerce")
    work["precio_unitario"] = pd.to_numeric(work["precio_unitario"], errors="coerce")

    ok = (
        work["unidades"].notna()
        & (work["unidades"] > 0)
        & work["precio_unitario"].notna()
        & (work["precio_unitario"] > 0)
    )

    validos = work.loc[ok].copy()
    errores = work.loc[~ok].copy()
    validos["importe"] = validos["unidades"] * validos["precio_unitario"]
    return validos, errores




if __name__ == "__main__":
    df = read_csv("datos", "ventas.csv")
    validos, errores = validar_ventas(df)
    importe_por_region = (
        validos.groupby("region", as_index=False)["importe"]
        .sum()
        .sort_values("importe", ascending=False)
    )
    print(importe_por_region)
    top_productos = (
        validos.groupby("producto", as_index=False)["importe"]
        .sum()
        .sort_values("importe", ascending=False)
        .head(3)
    )
    print(top_productos)
    save_clean_csv(validos, "datos", "ventas_limpias.csv")
    save_quality_json(df, validos, errores, "datos", "calidad_datos.json")

