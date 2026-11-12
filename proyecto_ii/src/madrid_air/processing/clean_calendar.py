import pandas as pd

from madrid_air.processing.common import csv_chunks


def clean(path):
    """Devuelve fecha, festivo (0/1) y laborable (0/1) según el CSV municipal."""
    frame = pd.concat(csv_chunks(path), ignore_index=True)
    kind = frame["laborable / festivo / domingo festivo"].str.strip().str.lower()
    allowed = {"laborable", "festivo", "domingo festivo", "sabado", "sábado", "domingo"}
    if not kind.isin(allowed).all():
        raise ValueError("Clasificación de calendario desconocida")
    return pd.DataFrame({
        "date": pd.to_datetime(frame.dia, dayfirst=True).dt.strftime("%Y-%m-%d"),
        "is_holiday": kind.str.contains("festivo").astype(int),
        "is_workday": kind.eq("laborable").astype(int),
    }).drop_duplicates("date", keep="last")
