import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ventas_app.metrics import drop_id, total_by_month, total_by_product, total_by_region


def test_total_por_region(ventas_con_importe):
    original = ventas_con_importe.copy(deep=True)

    resultado = total_by_region(ventas_con_importe)

    # Norte suma 20 + 20; Sur suma 30 + 5.
    assert isinstance(resultado, pd.Series)
    assert resultado.index.equals(ventas_con_importe.index)
    assert resultado.tolist() == pytest.approx([40, 35, 40, 35])
    assert_frame_equal(ventas_con_importe, original)


def test_total_por_mes(ventas_con_importe):
    original = ventas_con_importe.copy(deep=True)

    resultado = total_by_month(ventas_con_importe)

    # Enero de 2026 y enero de 2027 deben ser grupos distintos.
    assert isinstance(resultado, pd.Series)
    assert resultado.index.equals(ventas_con_importe.index)
    assert resultado.tolist() == pytest.approx([50, 50, 20, 5])
    assert_frame_equal(ventas_con_importe, original)


def test_total_por_producto(ventas_con_importe):
    original = ventas_con_importe.copy(deep=True)

    resultado = total_by_product(ventas_con_importe)

    # Sensor suma 20 + 30; Cable suma 20 + 5.
    assert isinstance(resultado, pd.Series)
    assert resultado.index.equals(ventas_con_importe.index)
    assert resultado.tolist() == pytest.approx([50, 50, 25, 25])
    assert_frame_equal(ventas_con_importe, original)


def test_total_por_region_sin_ventas(ventas_con_importe):
    ventas_vacias = ventas_con_importe.iloc[:0]
    resultado = total_by_region(ventas_vacias)
    assert isinstance(resultado, pd.Series)
    assert resultado.empty


def test_total_por_mes_sin_ventas(ventas_con_importe):
    ventas_vacias = ventas_con_importe.iloc[:0]
    resultado = total_by_month(ventas_vacias)
    assert isinstance(resultado, pd.Series)
    assert resultado.empty


def test_total_por_producto_sin_ventas(ventas_con_importe):
    ventas_vacias = ventas_con_importe.iloc[:0]
    resultado = total_by_product(ventas_vacias)
    assert isinstance(resultado, pd.Series)
    assert resultado.empty


def test_drop_id_elimina_solo_cliente_id(ventas):
    original = ventas.copy(deep=True)

    resultado = drop_id(ventas)

    assert "cliente_id" not in resultado.columns
    assert_frame_equal(resultado, original.drop(columns="cliente_id"))
    assert_frame_equal(ventas, original)
