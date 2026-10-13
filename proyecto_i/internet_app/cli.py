"""Carga los datos EPA, los valida y guarda un resumen educativo."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from internet_app.errors import DataLoadError
from internet_app.loader import load, save
from internet_app.metrics import (
    poblacion_estimada,
    poblacion_indicador,
    preparar_indicador,
    tasa_baja_formacion,
    tasa_participacion_formacion,
    tasa_ponderada,
)
from internet_app.validator import EPAValidator


BASE = Path(__file__).resolve().parent.parent


def preparar_datos(frame: pd.DataFrame, validador: EPAValidator) -> pd.DataFrame:
    """Valida los registros y prepara los códigos y pesos para las métricas."""
    validador.validar_valores(frame)
    datos = frame.copy()

    for columna in validador.TABLAS:
        datos[columna] = datos[columna].astype("string").str.strip()

    datos["FACTOREL"] = pd.to_numeric(datos["FACTOREL"], errors="coerce")
    return datos


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Calcula un resumen educativo de la EPA para personas de 20 a 24 años."
    )
    parser.add_argument("--input", required=True, help="Datos CSV o TAB")
    parser.add_argument("--output", required=True, help="CSV del resumen global")
    parser.add_argument(
        "--dictionary",
        default="data/dr_EPA_2026.json",
        help="Diccionario JSON con las descripciones y los códigos EPA",
    )
    args = parser.parse_args(argv)

    ruta_entrada = BASE / args.input
    ruta_salida = BASE / args.output
    ruta_diccionario = BASE / args.dictionary

    # El JSON explica los códigos que aparecen en el archivo de datos.
    diccionario = load(ruta_diccionario)
    if not isinstance(diccionario, dict):
        raise DataLoadError("El diccionario debe ser un objeto JSON")
    frame = load(ruta_entrada)
    if not isinstance(frame, pd.DataFrame):
        raise DataLoadError("Los datos deben ser un archivo CSV o TAB")

    validador = EPAValidator(diccionario)
    datos = preparar_datos(frame, validador)
    jovenes = preparar_indicador(datos)

    # Calculamos cada resultado una vez para guardarlo y mostrarlo.
    poblacion = poblacion_estimada(jovenes)
    poblacion_sin_estudios = poblacion_indicador(jovenes)
    tasa = tasa_ponderada(jovenes)
    tasa_nivel_bajo = tasa_baja_formacion(jovenes)
    tasa_formacion = tasa_participacion_formacion(jovenes)

    resultados = {
        "grupo_edad": "20-24",
        "registros": len(jovenes),
        "poblacion_estimada": poblacion,
        "poblacion_indicador": poblacion_sin_estudios,
        "tasa_indicador_20_24": tasa,
        "tasa_baja_formacion_20_24": tasa_nivel_bajo,
        "tasa_formacion_20_24": tasa_formacion,
    }
    resumen = pd.DataFrame([resultados])
    save(resumen, ruta_salida)

    print(f"Registros cargados: {len(datos)}")
    print(f"Personas de 20 a 24 años en la muestra: {len(jovenes)}")
    if tasa is None:
        print("Indicador: sin datos analizables")
    else:
        print(f"Población estimada: {poblacion:.2f}")
        print(f"Bajo nivel educativo sin formación reciente: {tasa:.2f}%")
        print(f"Bajo nivel educativo: {tasa_nivel_bajo:.2f}%")
        print(f"Participación en formación: {tasa_formacion:.2f}%")
    print("Este resumen analiza edades de 20 a 24 años; no reproduce la tasa oficial de 18 a 24.")
    logging.info("Resumen guardado: %s", ruta_salida)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
