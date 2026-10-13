from dataclasses import FrozenInstanceError

import pytest

from ventas_app.datos import SalesRecord


def test_importe_es_unidades_por_precio():
    venta = SalesRecord(region="Norte", product="Sensor", units=3, unit_price=12.5)

    assert venta.amount == pytest.approx(37.5)


def test_sales_record_es_inmutable():
    venta = SalesRecord(region="Norte", product="Sensor", units=3, unit_price=12.5)

    with pytest.raises(FrozenInstanceError):
        venta.units = 4
