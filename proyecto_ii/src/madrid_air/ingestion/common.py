import hashlib
import json
import logging
from pathlib import Path
import re

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from madrid_air.storage import atomic_path

LOG = logging.getLogger(__name__)
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def session():
    """Crea un cliente HTTP que reintenta fallos temporales hasta tres veces."""
    client = requests.Session()
    client.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    return client


def resources(client, dataset):
    """Consulta el catálogo y devuelve los archivos publicados para un dataset."""
    response = client.get("https://datos.madrid.es/api/3/action/package_show",
                          params={"id": dataset}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(f"Catálogo no disponible: {dataset}")
    return payload["result"]["resources"]


def period(resource):
    """Obtiene las fechas cubiertas por un recurso a partir de sus metadatos.

    Por ejemplo, 'Enero 2023' cubre ese mes y '2023' cubre todo el año.
    'Desde 2025' representa un recurso acumulado sin fecha final conocida.
    """
    text = " ".join(str(x.get("hierarchy_name", "")) for x in resource.get("hierarchy", []))
    if not text:
        text = resource.get("description", "")
    years = re.findall(r"\b20\d{2}\b", text)
    if not years:
        raise ValueError(f"Recurso sin periodo reconocible: {resource['id']}")
    month = None
    for month_number, month_name in enumerate(MONTHS, start=1):
        if month_name in text.lower():
            month = month_number
            break
    start = pd.Timestamp(int(years[0]), month or 1, 1)
    if "desde" in text.lower():
        end = pd.Timestamp.max.normalize()
    elif month:
        end = start + pd.offsets.MonthEnd(0)
    else:
        end = pd.Timestamp(int(years[-1]), 12, 31)
    return start, end


def download(client, url, folder, key, suffix, refresh=False):
    """Descarga un original a disco y devuelve su Path.

    key identifica el recurso; suffix indica su extensión (.csv, .zip o .json).
    Si refresh=False, reutiliza el archivo señalado por el índice, si existe.
    La huella SHA-256 depende del contenido: dos versiones distintas reciben
    nombres distintos. Así conservamos los originales anteriores y detectamos
    cuándo no hace falta repetir la limpieza. No es una clave ni un cifrado.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
    index = folder / f"{key}.json"
    if index.exists() and not refresh:
        saved = json.loads(index.read_text(encoding="utf-8"))
        cached = folder / saved["file"]
        if cached.exists():
            return cached
    LOG.info("Descargando %s", key)
    with atomic_path(folder / f"{key}.download") as temporary:
        # Escribimos y calculamos la huella por bloques de 1 MB: no cargamos
        # un ZIP de cientos de MB entero en memoria.
        digest = hashlib.sha256()
        with client.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with temporary.open("wb") as target:
                for block in response.iter_content(1024 * 1024):
                    target.write(block)
                    digest.update(block)
        filename = f"{key}-{digest.hexdigest()}{suffix}"
    (folder / f"{key}.download").replace(folder / filename)
    with atomic_path(index) as temporary:
        temporary.write_text(json.dumps({"file": filename, "url": url}), encoding="utf-8")
    return folder / filename


def municipal_files(client, settings, dataset, source, formats=("CSV", "ZIP")):
    """Entrega las rutas de las particiones que solapan las fechas solicitadas."""
    start, end = settings.bounds
    cutoff = end - pd.Timedelta(days=settings.overlap_days)
    candidates = []
    for resource in resources(client, dataset):
        if resource.get("format", "").upper() not in formats:
            continue
        resource_start, resource_end = period(resource)
        overlaps_requested_dates = resource_start <= end and resource_end >= start
        if overlaps_requested_dates:
            candidates.append((resource_start, resource_end, resource))
    if not candidates:
        raise ValueError(f"No hay recursos de {source} para el intervalo solicitado")
    # La fecha y el ID fijan un orden reproducible, de más antiguo a más reciente.
    candidates.sort(key=lambda item: (item[0], item[2]["id"]))
    for resource_start, resource_end, resource in candidates:
        needs_refresh = resource_end >= cutoff
        original_path = download(
            client, resource["url"], settings.root / "data/raw" / source,
            resource["id"], "." + resource["format"].lower(), refresh=needs_refresh,
        )
        yield original_path
