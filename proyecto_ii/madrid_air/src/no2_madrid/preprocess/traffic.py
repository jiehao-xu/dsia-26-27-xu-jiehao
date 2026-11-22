"""Limpia los intervalos originales de tráfico por bloques, sin agregarlos."""

import argparse
import gzip
from concurrent.futures import ProcessPoolExecutor
from time import monotonic

import pandas as pd

from no2_madrid.preprocess.common import (
    RAW_DIR, PROCESS_DIR, esta_actualizado, guardar_informe,
)

RENOMBRES = {
    "id": "ID_SENSOR", "fecha": "FECHA_HORA", "tipo_elem": "TIPO_ELEMENTO",
    "intensidad": "INTENSIDAD", "ocupacion": "OCUPACION", "carga": "CARGA",
    "vmed": "VELOCIDAD_MEDIA", "periodo_integracion": "PERIODO_INTEGRACION",
}
NUMERICAS = ["intensidad", "ocupacion", "carga", "vmed", "periodo_integracion"]


def limpiar(datos):
    datos = datos.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    datos["tipo_elem"] = datos["tipo_elem"].astype(str).str.strip().str.upper()
    for columna in NUMERICAS + ["id"]:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce").replace(
            [float("inf"), -float("inf")], float("nan"),
        )
    filas_validas = (
        datos["error"].astype(str).str.strip().eq("N")
        & datos["fecha"].notna() & datos["id"].gt(0)
        & datos["tipo_elem"].isin(["URB", "C30", "M30"])
        & datos["periodo_integracion"].gt(0)
    )
    datos = datos.loc[filas_validas].copy()
    datos["tipo_elem"] = datos["tipo_elem"].replace("M30", "C30")
    for columna in ["intensidad", "ocupacion", "carga", "vmed"]:
        datos[columna] = datos[columna].where(datos[columna].ge(0))
    for columna in ["ocupacion", "carga"]:
        datos[columna] = datos[columna].where(datos[columna].le(100))
    # La velocidad no está disponible en los sensores urbanos: sus ceros no son medidas.
    datos.loc[datos["tipo_elem"] == "URB", "vmed"] = float("nan")
    resultado = datos[list(RENOMBRES)].rename(columns=RENOMBRES)
    resultado["ID_SENSOR"] = resultado["ID_SENSOR"].astype("int64")
    resultado["PERIODO_INTEGRACION"] = resultado["PERIODO_INTEGRACION"].astype("int64")
    resultado["ANO"] = resultado["FECHA_HORA"].dt.year
    resultado["MES"] = resultado["FECHA_HORA"].dt.month
    resultado["DIA"] = resultado["FECHA_HORA"].dt.day
    return resultado[["FECHA_HORA", "ANO", "MES", "DIA", "ID_SENSOR", "TIPO_ELEMENTO",
                      "INTENSIDAD", "OCUPACION", "CARGA", "VELOCIDAD_MEDIA", "PERIODO_INTEGRACION"]]


def procesar_archivo(origen, destino, chunksize=500_000):
    inicio = monotonic()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".tmp")
    leidas = escritas = 0
    nulos = {columna: 0 for columna in ["INTENSIDAD", "OCUPACION", "CARGA", "VELOCIDAD_MEDIA"]}
    try:
        with gzip.open(temporal, "wt", encoding="utf-8", newline="", compresslevel=1) as salida:
            with pd.read_csv(origen, sep=";", encoding="utf-8-sig", chunksize=chunksize,
                             usecols=[*RENOMBRES, "error"]) as bloques:
                for bloque in bloques:
                    limpio = limpiar(bloque)
                    limpio.to_csv(salida, sep=";", index=False, header=leidas == 0,
                                  date_format="%Y-%m-%d %H:%M:%S")
                    leidas += len(bloque)
                    escritas += len(limpio)
                    for columna in nulos:
                        nulos[columna] += int(limpio[columna].isna().sum())
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    guardar_informe(origen, destino, filas_originales=leidas, filas_limpias=escritas,
                    filas_descartadas=leidas - escritas, valores_ausentes=nulos)
    print(f"Tráfico: {origen.parent.name}, {escritas:,}/{leidas:,} filas, "
          f"{monotonic() - inicio:.0f} s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mes", help="Procesar solo un mes, por ejemplo 2023_01")
    parser.add_argument("--forzar", action="store_true", help="Reprocesar resultados existentes")
    parser.add_argument("--workers", type=int, default=4, help="Meses en paralelo (por defecto 4)")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers debe ser al menos 1.")
    patron = f"trafico_{args.mes}" if args.mes else "trafico_*"
    archivos = sorted((RAW_DIR / "traffic").glob(f"{patron}/*.csv"))
    if not archivos:
        raise FileNotFoundError("No se encontraron CSV mensuales descomprimidos de tráfico.")
    pendientes = []
    for origen in archivos:
        destino = PROCESS_DIR / "traffic" / f"{origen.parent.name}.csv.gz"
        if not args.forzar and esta_actualizado(origen, destino):
            print(f"Ya está limpio: {destino.name}", flush=True)
            continue
        pendientes.append((origen, destino))
    if args.workers == 1:
        for origen, destino in pendientes:
            print(f"Limpiando: {origen.parent.name}", flush=True)
            procesar_archivo(origen, destino)
    else:
        print(f"Procesando {len(pendientes)} meses con {args.workers} procesos...", flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as ejecutor:
            tareas = [ejecutor.submit(procesar_archivo, origen, destino)
                      for origen, destino in pendientes]
            for tarea in tareas:
                tarea.result()


if __name__ == "__main__":
    main()
