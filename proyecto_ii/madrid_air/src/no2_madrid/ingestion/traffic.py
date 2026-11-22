# tiempo real: https://datos.madrid.es/dataset/202087-0-trafico-intensidad/downloads
# https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/downloads


import re
from pathlib import Path
from urllib.parse import urljoin
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup

URL = (
    "https://datos.madrid.es/dataset/"
    "208627-0-transporte-ptomedida-historico/downloads"
)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "traffic"
START_YEAR = 2023

MESES = {
    "Enero": 1, "Febrero": 2, "Marzo": 3,
    "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8,
    "Septiembre": 9, "Octubre": 10,
    "Noviembre": 11, "Diciembre": 12,
}


def obtener_enlaces():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    enlaces = {}

    anio = None
    mes = None

    # Recorremos las cabeceras y los enlaces en orden
    for elemento in soup.select("h3, a[href]"):
        if elemento.name == "h3":
            titulo = elemento.get_text(" ", strip=True)

            if re.fullmatch(r"20\d{2}", titulo):
                anio = int(titulo)
                mes = None
            elif titulo in MESES:
                mes = MESES[titulo]

        elif anio and mes and anio >= START_YEAR:
            href = elemento.get("href", "")

            if re.search(r"\.zip(?:\?.*)?$", href, re.I):
                enlaces[(anio, mes)] = urljoin(URL, href)

    return enlaces


def descargar_archivo(url, destino):
    temporal = destino.with_suffix(".tmp")

    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()

            with open(temporal, "wb") as archivo:
                for bloque in r.iter_content(chunk_size=1024 * 1024):
                    if bloque:
                        archivo.write(bloque)

        temporal.replace(destino)

    finally:
        temporal.unlink(missing_ok=True)


def descomprimir_archivo(origen, destino):
    destino = destino.resolve()

    with ZipFile(origen) as archivo:
        # Evitar que las rutas del ZIP escriban fuera de la carpeta del mes.
        for miembro in archivo.infolist():
            ruta = (destino / miembro.filename).resolve()
            if not ruta.is_relative_to(destino):
                raise ValueError(f"Ruta no válida dentro del ZIP: {miembro.filename}")

        destino.mkdir(parents=True, exist_ok=True)
        for miembro in archivo.infolist():
            ruta = destino / miembro.filename
            if (
                not miembro.is_dir()
                and ruta.is_file()
                and ruta.stat().st_size == miembro.file_size
            ):
                continue
            archivo.extract(miembro, destino)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    enlaces = obtener_enlaces()

    if not enlaces:
        raise RuntimeError(
            "No se encontraron enlaces ZIP. "
            "Comprueba si ha cambiado el portal."
        )

    for (anio, mes), url in sorted(enlaces.items()):
        destino = OUTPUT_DIR / f"trafico_{anio}_{mes:02d}.zip"

        if destino.exists():
            print(f"Ya existe: {destino.name}")
        else:
            print(f"Descargando: {destino.name}")
            descargar_archivo(url, destino)

        carpeta = destino.with_suffix("")
        print(f"Descomprimiendo: {destino.name} -> {carpeta}")
        descomprimir_archivo(destino, carpeta)

    print("Extracción terminada")


if __name__ == "__main__":
    main()
