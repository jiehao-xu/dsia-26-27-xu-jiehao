"""Contrato de las columnas EPA utilizadas en el analisis educativo.

Define nombres, descripciones, tablas de codigos y reglas de datos.
Los codigos y sus etiquetas se obtienen del diccionario JSON de la EPA.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from internet_app.errors import ValidationError


class EPARecord(BaseModel):
    """Contrato de una persona EPA; utiliza los nombres originales del fichero de entrada."""

    model_config = ConfigDict(extra="ignore")

    CCAA: Literal[
        "01",  # Andalucía
        "02",  # Aragón
        "03",  # Asturias, Principado de
        "04",  # Balears, Illes
        "05",  # Canarias
        "06",  # Cantabria
        "07",  # Castilla y León
        "08",  # Castilla-La Mancha
        "09",  # Cataluña
        "10",  # Comunitat Valenciana
        "11",  # Extremadura
        "12",  # Galicia
        "13",  # Madrid, Comunidad de
        "14",  # Murcia, Región de
        "15",  # Navarra, Comunidad Foral de
        "16",  # País Vasco
        "17",  # Rioja, La
        "51",  # Ceuta
        "52",  # Melilla
    ] = Field(description="Comunidad autonoma de residencia",
              json_schema_extra={"tabla": "TCCAA"})
    SEXO1: Literal[
        "1",  # Hombre
        "6",  # Mujer
    ] = Field(
        description="Sexo de la persona",
        json_schema_extra={"tabla": "TSEXO"},
    )
    NIVEL: Literal[
        "1",  # Persona de 16 o más años
        "2",  # Menor de 16 años
    ] = Field(
        description="Persona de 16 o mas anos o menor de 16",
        json_schema_extra={"tabla": "TNIVEL"},
    )
    EDAD1: Literal[
        "00",  # 0 a 4 años
        "05",  # 5 a 9 años
        "10",  # 10 a 15 años
        "16",  # 16 a 19 años
        "20",  # 20 a 24 años
        "25",  # 25 a 29 años
        "30",  # 30 a 34 años
        "35",  # 35 a 39 años
        "40",  # 40 a 44 años
        "45",  # 45 a 49 años
        "50",  # 50 a 54 años
        "55",  # 55 a 59 años
        "60",  # 60 a 64 años
        "65",  # 65 o más años
    ] = Field(description="Grupo de edad, no edad exacta",
              json_schema_extra={"tabla": "T5EDAD"})
    # Los tres campos educativos admiten None para menores de 16 años.
    NFORMA: Literal[
        "AN",  # Analfabetos
        "P1",  # Educación primaria incompleta
        "P2",  # Educación primaria
        "S1",  # Primera etapa de educación secundaria
        "SG",  # Segunda etapa de educación secundaria. Orientación general
        "SP",  # Segunda etapa de educación secundaria. Orientación profesional (incluye educación postsecundaria no superior)
        "SU",  # Educación superior
    ] | None = Field(
        description="Maximo nivel educativo alcanzado",
        json_schema_extra={"tabla": "TNFORMA"},
    )
    CURSR: Literal[
        "1",  # Sí
        "2",  # Estudiante en vacaciones
        "3",  # No
    ] | None = Field(
        description="Formacion reglada en las ultimas cuatro semanas",
        json_schema_extra={"tabla": "TCURSR"},
    )
    CURSNR: Literal[
        "1",  # Sí
        "2",  # Estudiante en vacaciones
        "3",  # No
    ] | None = Field(
        description="Formacion no reglada en las ultimas cuatro semanas",
        json_schema_extra={"tabla": "TCURSR"},
    )
    # No es un código: debe ser un número finito > 0. Su suma estima personas.
    FACTOREL: float = Field(
        gt=0, allow_inf_nan=False,
        description="Peso utilizado para estimar la poblacion",
        json_schema_extra={"tabla": None, "regla": "Numerico, finito y mayor que cero"},
    )

    @field_validator(
        "CCAA", "SEXO1", "NIVEL", "EDAD1",
        "NFORMA", "CURSR", "CURSNR", mode="before",
    )
    @classmethod
    def limpiar_codigo(cls, valor):
        if isinstance(valor, str):
            valor = valor.strip()
            if not valor:
                return None
        return valor

    @model_validator(mode="after")
    def comprobar_edad_y_estudios(self):
        menor = self.EDAD1 in {"00", "05", "10"}
        if menor != (self.NIVEL == "2"):
            raise ValueError("NIVEL y EDAD1 no corresponden")
        if self.NIVEL == "1":
            for nombre in ("NFORMA", "CURSR", "CURSNR"):
                if getattr(self, nombre) is None:
                    columna = nombre
                    raise ValueError(f"{columna}: es obligatorio para personas de 16 o mas anos")
        return self


# Los nombres y las descripciones se derivan del modelo, sin duplicar el esquema.
ESQUEMA = {
    nombre: {
        "nombre": nombre,
        "descripcion": campo.description,
        **(campo.json_schema_extra or {}),
    }
    for nombre, campo in EPARecord.model_fields.items()
}
COLUMNAS_OBLIGATORIAS = frozenset(ESQUEMA)
TABLAS = {
    columna: reglas["tabla"]
    for columna, reglas in ESQUEMA.items()
    if reglas["tabla"] is not None
}

def crear_contrato(diccionario: dict) -> dict:
    """Completa el esquema con las descripciones y valores del JSON.

    Devuelve un contrato independiente sin modificar ESQUEMA ni el JSON.
    """
    tablas = diccionario.get("codelists", {})
    for nombre in set(TABLAS.values()):
        if not isinstance(tablas.get(nombre), dict) or not tablas[nombre]:
            raise ValidationError(f"Falta la tabla de codigos: {nombre}")

    definiciones = {campo["name"]: campo for campo in diccionario.get("layout", [])}
    contrato = {}
    for columna, reglas in ESQUEMA.items():
        tabla = reglas["tabla"]
        contrato[columna] = {
            **reglas,
            "descripcion": definiciones.get(columna, {}).get(
                "description", reglas["descripcion"]
            ),
            "valores_permitidos": dict(tablas[tabla]) if tabla else None,
        }
    return contrato
