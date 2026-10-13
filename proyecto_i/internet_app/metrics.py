"""Indicador educativo ponderado para personas de 20 a 24 años.

No reproduce la tasa oficial de abandono de 18 a 24 años ni predice el futuro.
EDAD1 no permite separar los 18 y 19 años del grupo de 16 a 19.
"""

import pandas as pd


NIVELES_EDUCATIVOS_BAJOS = frozenset({"AN", "P1", "P2", "S1"})


def preparar_indicador(records: pd.DataFrame) -> pd.DataFrame:
    """Selecciona 20–24 años y añade el indicador educativo individual.

    CURSR/CURSNR = 3 significa ausencia de formación en las últimas cuatro
    semanas. El código 2 (vacaciones) no se considera ausencia de formación.
    """
    seleccion = records["NIVEL"].eq("1") & records["EDAD1"].eq("20")
    jovenes = records.loc[seleccion].copy()
    jovenes["baja_formacion"] = jovenes["NFORMA"].isin(NIVELES_EDUCATIVOS_BAJOS)
    jovenes["participa_formacion"] = (
        jovenes["CURSR"].isin({"1", "2"})
        | jovenes["CURSNR"].isin({"1", "2"})
    )
    jovenes["baja_formacion_sin_estudios"] = (
        jovenes["baja_formacion"] & ~jovenes["participa_formacion"]
    )
    return jovenes


def poblacion_estimada(jovenes: pd.DataFrame) -> float:
    """Suma los factores: población estimada en personas, no en miles.

    Las métricas reciben filas previamente validadas y preparadas con
    preparar_indicador(). No redondean los resultados para evitar perder precisión.
    """
    return float(jovenes["FACTOREL"].sum())


def poblacion_indicador(jovenes: pd.DataFrame) -> float:
    """Población estimada con baja formación y sin formación reciente."""
    cumplen = jovenes["baja_formacion_sin_estudios"]
    return float(jovenes.loc[cumplen, "FACTOREL"].sum())


def tasa_ponderada(jovenes: pd.DataFrame) -> float | None:
    """Porcentaje del indicador en la población analizable; None sin datos."""
    total = poblacion_estimada(jovenes)
    if total <= 0:
        return None
    return 100 * poblacion_indicador(jovenes) / total


def tasa_baja_formacion(jovenes: pd.DataFrame) -> float | None:
    """Porcentaje con nivel AN, P1, P2 o S1, estudien actualmente o no."""
    total = poblacion_estimada(jovenes)
    if total <= 0:
        return None
    peso = jovenes.loc[jovenes["baja_formacion"], "FACTOREL"].sum()
    return float(100 * peso / total)


def tasa_participacion_formacion(jovenes: pd.DataFrame) -> float | None:
    """Porcentaje en formación reglada o no reglada, incluyendo vacaciones."""
    total = poblacion_estimada(jovenes)
    if total <= 0:
        return None
    peso = jovenes.loc[jovenes["participa_formacion"], "FACTOREL"].sum()
    return float(100 * peso / total)



