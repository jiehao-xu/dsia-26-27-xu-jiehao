from copy import deepcopy

import pytest
from pydantic import BaseModel, ValidationError

from internet_app.contracts import EPARecord, crear_contrato


def test_esquema_incluye_codigos_y_descripciones_del_json(diccionario_epa):
    contrato = crear_contrato(diccionario_epa)
    nivel = contrato["NFORMA"]
    assert nivel["nombre"] == "NFORMA"
    assert nivel["valores_permitidos"] == diccionario_epa["codelists"]["TNFORMA"]
    campo = next(c for c in diccionario_epa["layout"] if c["name"] == "NFORMA")
    assert nivel["descripcion"] == campo["description"]
    assert contrato["FACTOREL"]["valores_permitidos"] is None
    assert "finito" in contrato["FACTOREL"]["regla"]



def test_contratos_no_comparten_valores_mutables(diccionario_epa):
    original = deepcopy(diccionario_epa)
    contrato = crear_contrato(diccionario_epa)
    otro = crear_contrato(diccionario_epa)
    contrato["CCAA"]["valores_permitidos"]["01"] = "otra etiqueta"
    assert otro["CCAA"]["valores_permitidos"]["01"] == "Andalucía"
    assert diccionario_epa == original


def test_modelo_conserva_nombres_originales_y_convierte_factor(personas_epa):
    persona = EPARecord.model_validate(personas_epa.loc[2].to_dict())
    assert isinstance(persona, BaseModel)
    assert persona.CCAA == "01"
    assert persona.FACTOREL == 100.0
    assert persona.model_dump(by_alias=True)["CCAA"] == "01"
    assert persona.model_dump()["EDAD1"] == "20"


def test_modelo_exige_nombres_originales(personas_epa):
    datos = personas_epa.loc[2].to_dict()
    datos["comunidad_autonoma"] = datos.pop("CCAA")
    with pytest.raises(ValidationError, match="CCAA"):
        EPARecord.model_validate(datos)


@pytest.mark.parametrize("factor", [0, -1, float("inf"), float("nan"), "texto"])
def test_modelo_rechaza_factor_invalido(personas_epa, factor):
    datos = personas_epa.loc[2].to_dict()
    datos["FACTOREL"] = factor
    with pytest.raises(ValidationError):
        EPARecord.model_validate(datos)


def test_modelo_rechaza_codigo_invalido(personas_epa):
    datos = personas_epa.loc[2].to_dict()
    datos["NFORMA"] = "desconocido"
    with pytest.raises(ValidationError):
        EPARecord.model_validate(datos)


def test_modelo_acepta_menor_sin_campos_educativos(personas_epa):
    datos = personas_epa.loc[15].to_dict()
    datos.update(NFORMA=None, CURSR=None, CURSNR=None)
    assert EPARecord.model_validate(datos).NIVEL == "2"


def test_modelo_exige_campos_educativos_en_adulto(personas_epa):
    datos = personas_epa.loc[2].to_dict()
    datos["NFORMA"] = None
    with pytest.raises(ValidationError, match="NFORMA"):
        EPARecord.model_validate(datos)


def test_modelo_rechaza_edad_incoherente(personas_epa):
    datos = personas_epa.loc[2].to_dict()
    datos["NIVEL"] = "2"
    with pytest.raises(ValidationError, match="no corresponden"):
        EPARecord.model_validate(datos)


def test_modelo_publica_descripciones_y_valores():
    schema = EPARecord.model_json_schema()
    assert schema["properties"]["SEXO1"]["enum"] == ["1", "6"]
    assert schema["properties"]["EDAD1"]["description"]
    assert schema["properties"]["FACTOREL"]["exclusiveMinimum"] == 0
