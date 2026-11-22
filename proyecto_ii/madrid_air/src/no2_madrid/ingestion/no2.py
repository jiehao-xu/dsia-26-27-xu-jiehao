"""Descarga los CSV originales de calidad del aire diaria de Madrid."""

import argparse
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://datos.madrid.es/dataset/201410-0-calidad-aire-diario/downloads"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "no2"
START_YEAR = 2023
END_YEAR = date.today().year


def obtener_enlaces(desde=START_YEAR, hasta=END_YEAR):
    with requests.get(URL, timeout=30) as response:
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

    enlaces = {}
    anio = None
    acumulado = False
    for elemento in soup.select("h3, a[href]"):
        if elemento.name == "h3":
            titulo = elemento.get_text(" ", strip=True)
            coincidencia = re.fullmatch(r"(Desde\s+)?(\d{4})", titulo, re.I)
            anio = int(coincidencia[2]) if coincidencia else None
            acumulado = bool(coincidencia and coincidencia[1])
        elif anio is not None:
            href = elemento.get("href", "")
            if urlparse(href).path.lower().endswith(".csv"):
                ultimo = END_YEAR if acumulado else anio
                for incluido in range(max(desde, anio), min(hasta, ultimo) + 1):
                    enlaces[incluido] = (urljoin(URL, href), acumulado)

    faltantes = sorted(set(range(desde, hasta + 1)) - enlaces.keys())
    if faltantes:
        raise RuntimeError(
            f"No se encontraron CSV para los años {faltantes}. "
            "Comprueba el rango y la estructura del portal."
        )
    return enlaces


def descargar_archivo(url, destino):
    temporal = destino.with_suffix(".tmp")
    try:
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            if "text/html" in response.headers.get("Content-Type", "").lower():
                raise RuntimeError(f"El portal devolvió HTML en lugar de CSV: {url}")
            with temporal.open("wb") as archivo:
                for bloque in response.iter_content(chunk_size=1024 * 1024):
                    if bloque:
                        archivo.write(bloque)
        if temporal.stat().st_size == 0:
            raise RuntimeError(f"El CSV descargado está vacío: {url}")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=int, default=START_YEAR)
    parser.add_argument("--hasta", type=int, default=END_YEAR)
    args = parser.parse_args()
    if not 2001 <= args.desde <= args.hasta <= END_YEAR:
        parser.error(f"El rango debe cumplir 2001 <= desde <= hasta <= {END_YEAR}.")

    enlaces = obtener_enlaces(args.desde, args.hasta)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    acumulados = {}
    for anio, (url, acumulado) in sorted(enlaces.items()):
        destino = OUTPUT_DIR / f"calidad_aire_diario_{anio}.csv"
        if acumulado:
            if url not in acumulados:
                # Este recurso contiene varios años y cambia con nuevos datos.
                print("Descargando CSV acumulado actualizado...", flush=True)
                with requests.get(url, timeout=120) as response:
                    response.raise_for_status()
                    acumulados[url] = pd.read_csv(
                        BytesIO(response.content), sep=";", dtype=str,
                        keep_default_na=False, encoding="utf-8-sig",
                    )
                if "ANO" not in acumulados[url].columns:
                    raise RuntimeError("El CSV acumulado no contiene la columna ANO.")
            datos = acumulados[url]
            datos = datos.loc[datos["ANO"].astype(int) == anio]
            if datos.empty:
                print(f"Sin datos publicados para {anio} todavía.", flush=True)
                continue
            temporal = destino.with_suffix(".tmp")
            try:
                datos.to_csv(temporal, sep=";", index=False)
                temporal.replace(destino)
            finally:
                temporal.unlink(missing_ok=True)
            print(f"Actualizado: {destino.name}", flush=True)
            continue
        if anio < END_YEAR and destino.is_file() and destino.stat().st_size > 0:
            print(f"Ya existe: {destino.name}", flush=True)
            continue
        print(f"Descargando: {destino.name}", flush=True)
        descargar_archivo(url, destino)

    print(f"Ingesta terminada ({args.desde}-{args.hasta}): {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
