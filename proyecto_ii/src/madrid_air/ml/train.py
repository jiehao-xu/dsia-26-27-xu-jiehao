import json

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

from madrid_air.integration.features import FEATURES, TARGET
from madrid_air.ml.evaluate import evaluate
from madrid_air.storage import atomic_path, read_csv


def train(root, trees=200):
    """Entrena con el pasado, evalúa con el periodo reciente y guarda el modelo.

    Entrada: data/final/dataset.csv. Salidas: random_forest.joblib y metrics.json.
    Devuelve las métricas para mostrarlas en la terminal. No usa reparto aleatorio
    porque en una predicción temporal no podemos entrenar con el futuro.
    """
    dataset = read_csv(root / "data/final/dataset.csv").sort_values("timestamp")
    usable = dataset.dropna(subset=[TARGET, "no2"])
    if len(usable) < 168:
        raise ValueError("Se necesitan al menos 168 pares horarios con NO2 y objetivo válidos.")
    split = int(len(usable) * 0.8)
    test = usable.iloc[split:]
    # Purga: ningún objetivo de entrenamiento alcanza el primer predictor de test.
    training = usable.iloc[:split]
    training = training.loc[training.target_timestamp < test.timestamp.iloc[0]]
    # La mediana se aprende SOLO de entrenamiento. Los indicadores permiten
    # distinguir un dato observado de otro que hemos rellenado.
    imputer = SimpleImputer(
        strategy="median", add_indicator=True, keep_empty_features=True,
    )
    forest = RandomForestRegressor(
        n_estimators=trees, min_samples_leaf=2, random_state=42, n_jobs=-1,
    )
    model = make_pipeline(imputer, forest)

    train_inputs = training[FEATURES]
    train_targets = training[TARGET]
    test_inputs = test[FEATURES]
    test_targets = test[TARGET]
    model.fit(train_inputs, train_targets)

    predictions = model.predict(test_inputs)
    persistence_predictions = test.no2  # Referencia: la próxima hora será igual a esta.
    metrics = evaluate(test_targets, predictions, persistence_predictions)
    metrics.update({"train_rows": len(training), "test_rows": len(test),
                    "train_end": str(training.timestamp.max()), "test_start": str(test.timestamp.min()),
                    "test_end": str(test.timestamp.max()),
                    "beats_baseline": metrics["mae"] < metrics["baseline_mae"]})
    # Se conserva el modelo evaluado. Reentrenar requiere ejecutar train explícitamente.
    with atomic_path(root / "models/random_forest.joblib") as path:
        joblib.dump({"model": model, "features": FEATURES, "metrics": metrics,
                     "horizon_hours": 1, "trained_at": str(pd.Timestamp.now(tz="UTC"))}, path)
    with atomic_path(root / "models/metrics.json") as path:
        path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics
