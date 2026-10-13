"""Validación de los datos EPA utilizados en el análisis educativo."""

import pandas as pd

from pydantic import ValidationError as PydanticValidationError

from internet_app.contracts import (
    COLUMNAS_OBLIGATORIAS, ESQUEMA, TABLAS, EPARecord, crear_contrato,
)
from internet_app.errors import ValidationError


class EPAValidator:

    NOMBRES_NORMALIZADOS = {
        "CCAA": "comunidad_autonoma",
        "SEXO1": "sexo",
        "NIVEL": "tipo_registro",
        "EDAD1": "grupo_edad",
        "NFORMA": "nivel_educativo",
        "CURSR": "formacion_reglada",
        "CURSNR": "formacion_no_reglada",
        "FACTOREL": "factor_elevacion",
    }

    ESQUEMA = ESQUEMA
    COLUMNAS_OBLIGATORIAS = COLUMNAS_OBLIGATORIAS
    TABLAS = TABLAS

    def __init__(self, diccionario: dict):
        self.esquema = crear_contrato(diccionario)
        self.tablas = {
            tabla: self.esquema[columna]["valores_permitidos"]
            for columna, tabla in self.TABLAS.items()
        }

    def validar_columnas(self, frame: pd.DataFrame) -> None:
        if frame.columns.duplicated().any():
            raise ValidationError("Hay columnas duplicadas")
        faltantes = self.COLUMNAS_OBLIGATORIAS - set(frame.columns)
        if faltantes:
            raise ValidationError(f"Faltan columnas: {', '.join(sorted(faltantes))}")

    def validar_valores(self, frame: pd.DataFrame) -> None:
        """Comprueba códigos, edad y factor; los campos educativos no se exigen a menores."""
        self.validar_columnas(frame)
        columnas = list(self.ESQUEMA)
        for indice, fila in frame[columnas].iterrows():
            valores = {columna: None if pd.isna(valor) else valor for columna, valor in fila.items()}
            try:
                persona = EPARecord.model_validate(valores)
            except PydanticValidationError as error:
                raise ValidationError(f"Fila {indice}: {error}") from error

            # El modelo valida tipos y reglas; el JSON confirma los codigos del fichero.
            for columna in self.TABLAS:
                valor = getattr(persona, columna)
                if valor is not None and valor not in self.esquema[columna]["valores_permitidos"]:
                    raise ValidationError(f"Fila {indice}: {columna}: codigo no incluido en el diccionario")

    def normalizar_columnas(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Renombra las columnas del esquema, manteniendo valores, índices y columnas extra."""
        self.validar_columnas(frame)
        resultado = frame.rename(columns=self.NOMBRES_NORMALIZADOS).copy()
        if resultado.columns.duplicated().any():
            raise ValidationError("La normalización produciría columnas duplicadas")
        return resultado
