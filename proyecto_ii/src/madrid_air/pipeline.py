"""Punto de unión del proyecto: descargar, limpiar, guardar y combinar.

Lee primero update() y build(). Las funciones auxiliares de abajo solo llevan
el registro de archivos procesados para evitar repetir trabajo.
"""
import hashlib
import logging

import pandas as pd

from madrid_air.ai.client import ResultsClient
from madrid_air.ai.report import interpret_prediction
from madrid_air.ingestion import aemet, calendar, no2, traffic
from madrid_air.ingestion.common import session
from madrid_air.integration.features import add_features
from madrid_air.integration.joins import join_sources
from madrid_air.processing import clean_aemet, clean_calendar, clean_no2, clean_traffic
from madrid_air.storage import read_csv, upsert, write_csv

LOG = logging.getLogger(__name__)
SOURCES = ("no2", "aemet", "traffic", "calendar")


def run(settings, retrain=False, ai_client: ResultsClient | None = None):
    """Job completo: datos → modelo sklearn → predicción local.

    Entrena si no existe un modelo; con retrain=True lo vuelve a entrenar.
    Si se proporciona ai_client, también interpreta la predicción y las métricas.
    Las funciones de abajo permiten ejecutar también cada etapa por separado.
    """
    from madrid_air.ml.train import train
    from madrid_air.ml.predict import predict

    update(settings)
    build(settings)
    model_path = settings.root / "models/random_forest.joblib"
    if retrain or not model_path.exists():
        LOG.info("Entrenando y evaluando Random Forest")
        train(settings.root)
    else:
        LOG.info("Reutilizando el modelo guardado; --retrain permite actualizarlo")
    prediction = predict(settings.root)
    if ai_client is not None:
        LOG.info("Interpretando predicción y métricas en modo %s", ai_client.mode)
        return interpret_prediction(settings.root, prediction, ai_client)
    return prediction


def analyze(settings, ai_client: ResultsClient, timestamp=None):
    """Predice e interpreta con el modelo existente; no descarga ni entrena."""
    from madrid_air.ml.predict import predict

    prediction = predict(settings.root, timestamp)
    return interpret_prediction(settings.root, prediction, ai_client)


def update(settings, sources=None):
    """Actualiza los CSV limpios de las fuentes elegidas, sin entrenar modelos."""
    settings.prepare()
    sources = list(sources or SOURCES)
    if "aemet" in sources and not settings.aemet_key:
        raise ValueError("Falta AEMET_API_KEY en .env. Puedes descargar las otras fuentes con --sources.")
    state_path = settings.root / "data/processed/ingestion_state.csv"
    if state_path.exists():
        state = pd.read_csv(state_path)
    else:
        state = pd.DataFrame(columns=["source", "file", "config"])

    with session() as client:
        for source in sources:
            # Cada rama hace visible qué descargador utiliza cada fuente.
            sensors = ()
            if source == "no2":
                original_files = no2.fetch(client, settings)
                keys = ["timestamp"]
            elif source == "aemet":
                original_files = aemet.fetch(client, settings)
                keys = ["date"]
            elif source == "traffic":
                sensors = traffic.select_sensors(client, settings)
                original_files = traffic.fetch(client, settings)
                keys = ["timestamp", "sensor_id"]
            elif source == "calendar":
                original_files = calendar.fetch(client, settings)
                keys = ["date"]
            else:
                raise ValueError(f"Fuente desconocida: {source}")

            output = settings.root / f"data/processed/{source}.csv"
            config = configuration_id(source, settings, sensors)
            previous = state.loc[state.source == source, "config"]
            if not previous.empty and not previous.eq(config).all():
                raise ValueError(f"Ha cambiado la configuración de {source}. Usa otro --root para no mezclar estaciones o sensores.")
            processed_files = set()
            if output.exists():
                same_configuration = (state.source == source) & (state.config == config)
                processed_files = set(state.loc[same_configuration, "file"])

            for path in original_files:
                if path.name in processed_files:
                    continue
                LOG.info("Limpiando %s", path.name)
                if source == "no2":
                    clean_data = clean_no2.clean(path)
                elif source == "aemet":
                    clean_data = clean_aemet.clean(path)
                elif source == "traffic":
                    clean_data = clean_traffic.clean(path, sensors)
                else:
                    clean_data = clean_calendar.clean(path)

                # Primero guardamos los datos. Solo después anotamos que terminamos.
                # Si falla entre ambos pasos, repetir el upsert no genera duplicados.
                upsert(clean_data, output, keys)
                state = record_processed_file(state, state_path, source, path, config)
            if not output.exists():
                raise ValueError(f"No se obtuvieron datos de {source}.")
            if source == "traffic":
                current = read_csv(output)
                write_csv(current.loc[current.sensor_id.isin(sensors)], output)


def build(settings):
    """Lee los cuatro CSV, los une por hora y guarda dataset.csv y coverage.csv."""
    settings.prepare()
    for source in SOURCES:
        path = settings.root / f"data/processed/{source}.csv"
        if not path.exists():
            raise ValueError(f"Falta {path}; ejecuta update primero.")

    processed_folder = settings.root / "data/processed"
    no2_data = read_csv(processed_folder / "no2.csv")
    weather_data = read_csv(processed_folder / "aemet.csv")
    traffic_data = read_csv(processed_folder / "traffic.csv")
    calendar_data = read_csv(processed_folder / "calendar.csv")
    start, end = settings.bounds
    joined = join_sources(
        no2_data, weather_data, traffic_data, calendar_data,
        start, end, settings.aemet_lag_days,
    )
    dataset = add_features(joined)
    write_csv(dataset, settings.root / "data/final/dataset.csv")
    coverage = pd.DataFrame({"column": dataset.columns,
                             "present": dataset.notna().sum().values,
                             "missing": dataset.isna().sum().values})
    write_csv(coverage, settings.root / "data/final/coverage.csv")
    LOG.info("Dataset: %d horas, %d objetivos disponibles", len(dataset), dataset.target_no2.notna().sum())
    return dataset


def configuration_id(source, settings, sensors):
    """Identificador estable para impedir mezclar estaciones o sensores distintos.

    SHA-256 convierte la configuración en una huella de texto. Se conserva este
    formato para poder reutilizar ingestion_state.csv de ejecuciones anteriores.
    No se incluye la clave privada de AEMET.
    """
    if source == "aemet":
        identity = settings.aemet_station
    else:
        identity = sorted(sensors)
    return hashlib.sha256(str(identity).encode()).hexdigest()


def record_processed_file(state, state_path, source, original_path, config):
    """Anota un original ya guardado para no volver a limpiarlo sin cambios."""
    entry = pd.DataFrame([{
        "source": source,
        "file": original_path.name,
        "config": config,
    }])
    updated_state = pd.concat([state, entry], ignore_index=True).drop_duplicates()
    write_csv(updated_state, state_path)
    return updated_state
