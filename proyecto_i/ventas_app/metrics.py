"""
agregaciones / KPIs
"""
from dataclasses import dataclass    
from ventas_app.datos import SalesRecord
import pandas as pd


def total_by_region(records: pd.DataFrame) -> dict[str, float]:
    """
    Calcular el importe total por region
    """
    return records.groupby("region")["importe"].transform("sum")
    
def drop_id(records: pd.DataFrame) -> pd.DataFrame:
    """
    Eliminar la columna id
    """
    return records.drop(columns=["cliente_id"])

def total_by_month(records: pd.DataFrame) -> dict[str, float]:
    """
    Calcular el importe total por mes
    """
    fechas = pd.to_datetime(records["fecha"], errors="coerce")
    return records.groupby(fechas.dt.to_period("M"))["importe"].transform("sum")

def total_by_product(records: pd.DataFrame) -> dict[str, float]:
    """
    Calcular el total por producto
    """
    return records.groupby("producto")["importe"].transform("sum")





    


