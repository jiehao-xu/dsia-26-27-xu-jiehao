import pandas as pd
import pytest


@pytest.fixture
def ventas():
    """Ventas de ejemplo con totales conocidos e índices no consecutivos."""
    return pd.DataFrame({
        "fecha": ["2026-01-09", "2026-01-20", "2026-02-05", "2027-01-09"],
        "region": ["Norte", "Sur", "Norte", "Sur"],
        "producto": ["Sensor", "Sensor", "Cable", "Cable"],
        "unidades": [2, 3, 4, 1],
        "precio_unitario": [10.0, 10.0, 5.0, 5.0],
        "cliente_id": ["C001", "C002", "C003", "C004"],
    }, index=[2, 5, 9, 12])


@pytest.fixture
def ventas_con_importe(ventas):
    frame = ventas.copy()
    frame["importe"] = [20.0, 30.0, 20.0, 5.0]
    return frame
