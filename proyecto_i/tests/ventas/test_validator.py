import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ventas_app.errors import ValidationError
from ventas_app.validator import SalesValidator


def test_acepta_las_columnas_obligatorias(ventas):
    validador = SalesValidator()
    validador.validar_columnas(ventas)


def test_acepta_columnas_adicionales(ventas):
    ventas["observaciones"] = "ok"
    validador = SalesValidator()
    validador.validar_columnas(ventas)


@pytest.mark.parametrize("columna", [
    "fecha", "region", "producto", "unidades", "precio_unitario", "cliente_id",
])
def test_columna_ausente_lanza_error(ventas, columna):
    ventas_incompletas = ventas.drop(columns=columna)
    validador = SalesValidator()

    with pytest.raises(ValidationError, match=columna):
        validador.validar_columnas(ventas_incompletas)


def test_informa_de_todas_las_columnas_ausentes(ventas):
    ventas_incompletas = ventas.drop(columns=["fecha", "region"])
    validador = SalesValidator()

    with pytest.raises(ValidationError) as error:
        validador.validar_columnas(ventas_incompletas)

    assert "fecha" in str(error.value)
    assert "region" in str(error.value)


@pytest.mark.parametrize("fecha", ["2026-01-09", "2024-02-29"])
def test_fecha_valida(fecha):
    datos = pd.DataFrame({"fecha": [fecha]})
    validador = SalesValidator()
    validador.validar_fechas(datos)


@pytest.mark.parametrize("fecha", ["2026-02-29", "2026-02-30", "2026-13-01", "texto", "", None])
def test_fecha_invalida_lanza_error(fecha):
    datos = pd.DataFrame({"fecha": [fecha]})
    validador = SalesValidator()

    with pytest.raises(ValidationError):
        validador.validar_fechas(datos)


def test_fecha_invalida_detiene_validacion_aunque_haya_fechas_validas():
    frame = pd.DataFrame({"fecha": ["2026-01-09", "incorrecta"]})
    with pytest.raises(ValidationError, match="1"):
        SalesValidator().validar_fechas(frame)


@pytest.mark.parametrize("columna", ["unidades", "precio_unitario"])
@pytest.mark.parametrize("valor", [0, -1, "texto", "", None])
def test_valores_invalidos_separados(columna, valor):
    datos = pd.DataFrame({"unidades": [2], "precio_unitario": [10.0]}, dtype=object)
    datos.loc[0, columna] = valor
    validador = SalesValidator()

    validos, errores = validador.validar_ventas(datos)

    assert validos.empty
    assert errores.index.tolist() == [0]
    assert "importe" not in errores.columns


def test_convierte_texto_numerico_y_calcula_importe():
    datos = pd.DataFrame({"unidades": ["3"], "precio_unitario": ["12.5"]})
    validador = SalesValidator()

    validos, errores = validador.validar_ventas(datos)

    assert errores.empty
    assert validos.loc[0, "importe"] == pytest.approx(37.5)


def test_separa_filas_sin_modificar_original(ventas):
    ventas.loc[5, "unidades"] = 0
    original = ventas.copy(deep=True)

    validos, errores = SalesValidator().validar_ventas(ventas)

    assert validos.index.tolist() == [2, 9, 12]
    assert errores.index.tolist() == [5]
    assert validos["importe"].tolist() == pytest.approx([20, 20, 5])
    assert len(validos) + len(errores) == len(ventas)
    assert_frame_equal(ventas, original)


def test_dataframe_vacio_con_columnas(ventas):
    frame = ventas.iloc[:0]
    validator = SalesValidator()
    validator.validar_columnas(frame)
    validator.validar_fechas(frame)
    validos, errores = validator.validar_ventas(frame)
    assert validos.empty
    assert errores.empty
    assert "importe" in validos.columns
