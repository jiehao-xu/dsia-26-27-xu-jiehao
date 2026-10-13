import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from internet_app.errors import ValidationError
from internet_app.validator import EPAValidator


def test_acepta_columnas_sin_modificar_datos(personas_epa, diccionario_epa):
    original = personas_epa.copy(deep=True)
    EPAValidator(diccionario_epa).validar_columnas(personas_epa)
    assert_frame_equal(personas_epa, original)


@pytest.mark.parametrize("columna", ["CCAA", "SEXO1", "NIVEL", "EDAD1", "NFORMA", "CURSR", "CURSNR", "FACTOREL"])
def test_falta_columna(personas_epa, diccionario_epa, columna):
    datos = personas_epa.drop(columns=columna)
    with pytest.raises(ValidationError, match=columna):
        EPAValidator(diccionario_epa).validar_columnas(datos)


def test_columnas_duplicadas(personas_epa, diccionario_epa):
    datos = pd.concat([personas_epa, personas_epa[["CCAA"]]], axis=1)
    with pytest.raises(ValidationError, match="duplicadas"):
        EPAValidator(diccionario_epa).validar_columnas(datos)


def test_acepta_columna_adicional(personas_epa, diccionario_epa):
    personas_epa["extra"] = "dato"
    EPAValidator(diccionario_epa).validar_columnas(personas_epa)


def test_diccionario_incompleto():
    with pytest.raises(ValidationError, match="tabla"):
        EPAValidator({})


def test_columnas_presentes_sin_filas(personas_epa, diccionario_epa):
    EPAValidator(diccionario_epa).validar_columnas(personas_epa.iloc[:0])


def test_normalizar_columnas_conserva_valores_y_original(personas_epa, diccionario_epa):
    original = personas_epa.copy(deep=True)
    personas_epa["extra"] = "dato"
    resultado = EPAValidator(diccionario_epa).normalizar_columnas(personas_epa)
    assert resultado.columns.tolist() == [
        "comunidad_autonoma", "sexo", "tipo_registro", "grupo_edad",
        "nivel_educativo", "formacion_reglada", "formacion_no_reglada",
        "factor_elevacion", "extra",
    ]
    assert resultado.loc[2, "comunidad_autonoma"] == "01"
    assert resultado.index.equals(personas_epa.index)
    assert_frame_equal(personas_epa.drop(columns="extra"), original)


def test_normalizar_rechaza_nombres_que_colisionan(personas_epa, diccionario_epa):
    personas_epa["comunidad_autonoma"] = "otra columna"
    with pytest.raises(ValidationError, match="duplicadas"):
        EPAValidator(diccionario_epa).normalizar_columnas(personas_epa)


def test_validar_valores_rechaza_codigo_desconocido(personas_epa, diccionario_epa):
    personas_epa.loc[2, "NFORMA"] = "desconocido"
    with pytest.raises(ValidationError, match="NFORMA"):
        EPAValidator(diccionario_epa).validar_valores(personas_epa)


def test_validar_valores_acepta_codigos_con_espacios(personas_epa, diccionario_epa):
    personas_epa.loc[2, "CCAA"] = " 01 "
    EPAValidator(diccionario_epa).validar_valores(personas_epa)


def test_metodos_con_dataframe_vacio(personas_epa, diccionario_epa):
    validador = EPAValidator(diccionario_epa)
    vacio = personas_epa.iloc[:0]
    validador.validar_valores(vacio)
    assert validador.normalizar_columnas(vacio).empty
