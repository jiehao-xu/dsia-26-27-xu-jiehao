"""Climatologías diarias AEMET por meses; se conservan los originales JSON."""
import json

import pandas as pd

from madrid_air.ingestion.common import download


def fetch(client, settings):
    """Descarga el histórico diario y entrega una ruta de archivo por mes.

    ``client`` es una sesión HTTP y ``settings`` contiene fechas, estación y clave.
    No devuelve un DataFrame: la limpieza del JSON corresponde a clean_aemet.py.
    ``yield`` entrega una ruta cada vez, para procesar los meses de uno en uno.
    """
    if not settings.aemet_key:
        raise ValueError("Configura AEMET_API_KEY en .env para descargar AEMET.")
    start_date, end_date = settings.bounds
    # Para predecir el 1 de enero con meteorología de 7 días antes,
    # también necesitamos descargar los últimos días de diciembre.
    start_date -= pd.Timedelta(days=settings.aemet_lag_days)
    refresh_from = end_date - pd.Timedelta(days=settings.overlap_days)
    raw_folder = settings.root / "data/raw/aemet"

    for month in pd.period_range(start_date, end_date, freq="M"):
        month_start = month.start_time
        month_end = min(month.end_time.normalize(), end_date)
        download_name = f"{settings.aemet_station}-{month_start.date()}-{month_end.date()}"
        index_path = raw_folder / f"{download_name}.json"

        # El índice es un pequeño JSON que indica dónde guardamos el original.
        # Los meses antiguos se reutilizan; los recientes pueden tener correcciones.
        if month_end < refresh_from and index_path.exists():
            download_index = json.loads(index_path.read_text(encoding="utf-8"))
            cached_path = raw_folder / download_index["file"]
            if cached_path.exists():
                yield cached_path
                continue

        # AEMET requiere dos peticiones: la primera devuelve una URL en "datos";
        # la segunda, realizada por download(), descarga las observaciones.
        endpoint = ("https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos/"
                    f"fechaini/{month_start:%Y-%m-%d}T00:00:00UTC/"
                    f"fechafin/{month_end:%Y-%m-%d}T23:59:59UTC/"
                    f"estacion/{settings.aemet_station}")
        response = client.get(endpoint, headers={"api_key": settings.aemet_key}, timeout=60)
        response.raise_for_status()
        api_response = response.json()
        status = int(api_response.get("estado", 0))
        if status == 404:
            # No hay datos publicados para este mes. No fabricamos observaciones.
            continue
        if status != 200 or not api_response.get("datos"):
            raise ValueError(f"AEMET sin respuesta válida para {month_start:%Y-%m}: estado {status}")

        observations_url = api_response["datos"]
        original_path = download(
            client, observations_url, raw_folder, download_name, ".json", refresh=True
        )
        yield original_path
