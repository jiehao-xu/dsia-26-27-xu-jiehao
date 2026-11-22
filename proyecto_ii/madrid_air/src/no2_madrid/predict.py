"""Carga de artefacto local, inferencia y resumen tolerante a fallos de IA."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from no2_madrid.clients.base import PredictionContext
from no2_madrid.clients.mock import MockClient
from no2_madrid.config import Settings
from no2_madrid.dataset import data_contract
from no2_madrid.features import make_features
from no2_madrid.io import write_json
from no2_madrid.train import load_daily

log = logging.getLogger(__name__)


def predict(settings: Settings, date=None, client=None, *, model_path=None, dataset_path=None):
    dataset_path = Path(dataset_path) if dataset_path is not None else settings.dataset_path
    # joblib sólo debe cargar artefactos locales de confianza.
    artifact = joblib.load(model_path if model_path is not None else settings.model_path)
    meta, model = artifact["metadata"], artifact["model"]
    if json.loads(json.dumps(meta["contract"])) != json.loads(json.dumps(data_contract(settings))):
        raise ValueError("La configuración no coincide con la del modelo: reentrena o restaura la configuración.")
    daily = load_daily(settings, dataset_path)
    dataset_meta = json.loads(dataset_path.with_suffix(".json").read_text(encoding="utf-8"))
    if meta["no2_stations"] != dataset_meta["no2_stations"]:
        raise ValueError("La red de estaciones NO₂ ha cambiado: reentrena el modelo.")
    target = pd.Timestamp(date) if date else daily.NO2.dropna().index.max() + pd.Timedelta(days=1)
    if target <= pd.Timestamp(meta["trained_through"]):
        raise ValueError("La fecha debe ser posterior al último día usado para entrenar el artefacto.")
    if target not in daily.index:
        raise ValueError("Fecha fuera del dataset. Actualiza las fuentes y ejecuta build-dataset.")
    x = make_features(daily, settings)
    if pd.isna(x.loc[target, f"no2_lag_{settings.no2_lag_days}"]):
        raise ValueError("Falta el NO₂ de referencia necesario para predecir esa fecha.")
    row = x.loc[[target], meta["features"]]
    prediction = float(np.asarray(model.predict(row)).reshape(-1)[0])
    if not np.isfinite(prediction):
        raise ValueError("Predicción no finita.")
    prediction = max(0., prediction)
    context = PredictionContext(str(target.date()), "Madrid", prediction,
                                int(row.isna().sum().sum()), meta["test_metrics"]["mae"], len(meta["no2_stations"]))
    status, explanation = settings.ai_mode, ""
    try:
        if client is None:
            if settings.ai_mode == "mock":
                client = MockClient()
            else:
                from no2_madrid.clients.google import GoogleClient
                client = GoogleClient(settings.google_api_key, settings.google_model)
        explanation = client.explain(context)
        if not explanation.strip():
            raise ValueError("Interpretación vacía.")
    except Exception as exc:
        # No imprimir el mensaje de un SDK: podría contener URL o credenciales.
        log.warning("Interpretación no disponible (%s); se usa plantilla.", type(exc).__name__)
        status, explanation = "fallback", MockClient().explain(context)
    reference = target - pd.Timedelta(days=settings.no2_lag_days)
    result = {"date": context.date, "scope": "Madrid", "target_definition": dataset_meta["target_definition"],
              "network_station_count": len(meta["no2_stations"]),
              "network_station_ids": meta["no2_stations"],
              "min_station_coverage": settings.min_station_coverage, "no2": prediction,
              "unit": "µg/m³", "model": meta["selected"], "model_created_utc": meta["created_utc"],
              "trained_through": meta["trained_through"], "historical_simulation": True,
              "information_cutoffs": {"no2": str((target-pd.Timedelta(days=settings.no2_lag_days)).date()),
                  "meteo": str((target-pd.Timedelta(days=settings.meteo_lag_days)).date()),
                  "traffic": str((target-pd.Timedelta(days=settings.traffic_lag_days)).date())},
              "missing_features": context.missing_features, "n_features": len(row.columns),
              "missing_feature_names": row.columns[row.isna().iloc[0]].tolist(),
              "input_no2_coverage": {"date": str(reference.date()),
                  "valid_stations": int(daily.loc[reference, "NO2_N_ESTACIONES"]),
                  "fraction": float(daily.loc[reference, "NO2_COBERTURA"])},
              "test_mae": context.test_mae, "ai_status": status, "ai_provider": settings.ai_provider,
              "ai_model": settings.google_model if status == "real" else None,
              "explanation": explanation,
              "generated_utc": datetime.now(timezone.utc).isoformat()}
    write_json(settings.output_dir / "reports" / "runs" / f"prediction_{context.date}.json", result)
    return result
