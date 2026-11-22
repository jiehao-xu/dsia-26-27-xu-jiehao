"""Descarga los datos meteorológicos horarios de Madrid desde 2023."""

import argparse
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://datos.madrid.es/dataset/300352-0-meteorologicos-horarios/downloads"
OUTPUT_DIR = Path("data") / "raw" / "meteorologia_municipal"
START_YEAR = 2023
END_YEAR = date.today().year
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def consultar(url):
    # Reintentar fallos temporales del portal sin esperar dos minutos por intento.
    with requests.Session() as sesion:
        sesion.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        )))
        response = sesion.get(url, timeout=(15, 30))
        response.raise_for_status()
        return response


def obtener_enlaces(desde=START_YEAR, hasta=END_YEAR):
    with consultar(URL) as response:
        soup = BeautifulSoup(response.content, "html.parser")

    enlaces = {}
    anio, mes, acumulado = None, None, False
    for elemento in soup.select("h3, a[href]"):
        if elemento.name == "h3":
            titulo = elemento.get_text(" ", strip=True).lower()
            coincidencia = re.fullmatch(r"(desde\s+)?(\d{4})", titulo)
            if coincidencia:
                anio = int(coincidencia[2])
                acumulado = bool(coincidencia[1])
                mes = None
            elif titulo in MESES:
                mes = MESES[titulo]
            else:
                anio, mes, acumulado = None, None, False
        elif anio is not None:
            href = elemento.get("href", "")
            if urlparse(href).path.lower().endswith(".csv"):
                url = urljoin(URL, href)
                if acumulado:
                    for incluido in range(max(desde, anio), hasta + 1):
                        enlaces.setdefault(incluido, {})[None] = url
                elif desde <= anio <= hasta and mes is not None:
                    enlaces.setdefault(anio, {})[mes] = url

    for esperado in range(desde, hasta + 1):
        recursos = enlaces.get(esperado, {})
        if not recursos:
            raise RuntimeError(f"No se encontraron CSV para {esperado}.")
        if None not in recursos and esperado < END_YEAR:
            faltantes = sorted(set(range(1, 13)) - recursos.keys())
            if faltantes:
                raise RuntimeError(f"Faltan enlaces de los meses {faltantes} de {esperado}.")
    return enlaces


def leer_csv(url):
    with consultar(url) as response:
        datos = pd.read_csv(
            BytesIO(response.content), sep=";", dtype=str,
            keep_default_na=False, encoding="utf-8-sig",
        )
    requeridas = {"ANO", "MES", "DIA", "ESTACION", "MAGNITUD", "H01", "V01", "H24", "V24"}
    if not requeridas <= set(datos.columns) or datos.empty:
        raise RuntimeError(f"CSV meteorológico vacío o con formato inesperado: {url}")
    return datos


def guardar_csv(datos, destino):
    temporal = destino.with_suffix(".tmp")
    try:
        datos.to_csv(temporal, sep=";", index=False)
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=int, default=START_YEAR)
    parser.add_argument("--hasta", type=int, default=END_YEAR)
    args = parser.parse_args()
    if not 2019 <= args.desde <= args.hasta <= END_YEAR:
        parser.error(f"El rango debe cumplir 2019 <= desde <= hasta <= {END_YEAR}.")

    enlaces = obtener_enlaces(args.desde, args.hasta)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    acumulados = {}
    for anio, recursos in sorted(enlaces.items()):
        destino = OUTPUT_DIR / f"meteorologicos_horarios_{anio}.csv"
        if None in recursos:
            url = recursos[None]
            if url not in acumulados:
                print("Descargando CSV meteorológico acumulado actualizado...", flush=True)
                acumulados[url] = leer_csv(url)
            datos = acumulados[url]
            datos = datos.loc[datos["ANO"].astype(int) == anio]
            if datos.empty:
                print(f"Sin datos publicados para {anio} todavía.", flush=True)
                continue
        else:
            if anio < END_YEAR and destino.is_file() and destino.stat().st_size > 0:
                print(f"Ya existe: {destino.name}", flush=True)
                continue
            partes = []
            for mes, url in sorted(recursos.items()):
                print(f"Descargando meteorología: {anio}-{mes:02d}", flush=True)
                parte = leer_csv(url)
                if set(parte["ANO"].astype(int)) != {anio} or set(parte["MES"].astype(int)) != {mes}:
                    raise RuntimeError(f"El CSV no corresponde a {anio}-{mes:02d}: {url}")
                partes.append(parte)
            datos = pd.concat(partes, ignore_index=True)
        guardar_csv(datos, destino)
        print(f"Guardado: {destino.name} ({len(datos)} registros)", flush=True)

    print(f"Ingesta terminada ({args.desde}-{args.hasta}): {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
