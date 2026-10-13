"""
reglas de negocio / calidad
"""

import pandas as pd
from ventas_app.errors import ValidationError

class SalesValidator:

    COLUMNAS_OBLIGATORIAS = frozenset({
        "fecha",
        "region",
        "producto",
        "unidades",
        "precio_unitario",
        "cliente_id",

    })

    def validar_columnas(self, frame: pd.DataFrame) -> None:
        """
        Comprueba que no falta ninguna columna
        """
        faltantes = self.COLUMNAS_OBLIGATORIAS - set(frame.columns)

        if faltantes:
            raise ValidationError(
                f"Faltan las columnas obligatorias: {faltantes}"
            )
    
    def validar_ventas(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Reglas mínimas:
            unidades numérica y > 0
            precio_unitario numérico y > 0
            columnas derivadas: importe = unidades * precio_unitario solo en válidos
        Devuelve (validos, errores)
        """
        work = frame.copy()
        work["unidades"] = pd.to_numeric(work["unidades"], errors="coerce")
        work["precio_unitario"] = pd.to_numeric(work["precio_unitario"], errors="coerce")

        ok = (
            work["unidades"].notna()
            & (work["unidades"] > 0)
            & work["precio_unitario"].notna()
            & (work["precio_unitario"] > 0)
        )

        validos = work.loc[ok].copy()
        errores = work.loc[~ok].copy()
        validos["importe"] = validos["unidades"] * validos["precio_unitario"]
        return validos, errores

    def validar_fechas(self, frame: pd.DataFrame):
        """
        Comprueba que todas las fechas sigan el formato AAAA-MM-DD
        """
        fechas = pd.to_datetime(
            frame["fecha"],
            format="%Y-%m-%d",
            errors="coerce"

        )
        fecha_validas = fechas.notna()
        numero_invalidas = (~fecha_validas).sum()
        if numero_invalidas:
            raise ValidationError(
                f"{numero_invalidas} no siguen el formato %Y-%m-%d"
            )

