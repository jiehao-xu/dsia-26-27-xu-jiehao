"""Selección en validación temporal y evaluación final reservada."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from no2_madrid.config import Settings
from no2_madrid.dataset import data_contract
from no2_madrid.features import make_features
from no2_madrid.io import sha256, write_json

log = logging.getLogger(__name__)


def metrics(y, prediction):
    return {"mae": float(mean_absolute_error(y, prediction)),
            "rmse": float(np.sqrt(mean_squared_error(y, prediction))), "n": len(y)}


def load_daily(settings, dataset_path=None):
    dataset_path = Path(dataset_path) if dataset_path is not None else settings.dataset_path
    daily = pd.read_csv(dataset_path, sep=";", parse_dates=["FECHA"]).set_index("FECHA")
    meta = json.loads(dataset_path.with_suffix(".json").read_text(encoding="utf-8"))
    # JSON normaliza tuplas como listas.
    expected = json.loads(json.dumps(data_contract(settings)))
    if meta["contract"] != expected or meta["dataset_sha256"] != sha256(dataset_path):
        raise ValueError("Dataset/configuración incompatibles o archivo modificado: ejecuta build-dataset.")
    return daily


def train(settings: Settings, train_end="2024-12-31", validation_end="2025-12-31"):
    daily = load_daily(settings)
    x = make_features(daily, settings)
    baseline_column = f"no2_lag_{settings.no2_lag_days}"
    eligible = daily.NO2.notna() & x[baseline_column].notna()
    x, y = x.loc[eligible], daily.loc[eligible, "NO2"]
    train_end, validation_end = pd.Timestamp(train_end), pd.Timestamp(validation_end)
    if train_end >= validation_end:
        raise ValueError("train-end debe ser anterior a validation-end.")
    masks = {"train": x.index <= train_end,
             "validation": (x.index > train_end) & (x.index <= validation_end),
             "test": x.index > validation_end}
    for label, mask in masks.items():
        if mask.sum() < 10:
            raise ValueError(f"La partición {label} necesita al menos 10 días válidos; revisa fechas/cobertura.")
    basic = [c for c in x if not c.startswith(("METEO_", "TRAFICO_"))]
    no_traffic = [c for c in x if not c.startswith("TRAFICO_")]
    specs = {"ridge_basic": ("ridge", basic),
             "ridge_no_traffic": ("ridge", no_traffic), "ridge_full": ("ridge", list(x.columns)),
             "hist_no_traffic": ("hist", no_traffic), "hist_full": ("hist", list(x.columns))}
    report = {"unit": "µg/m³", "partitions": {}, "validation": {}, "test": {}, "missing_features": {}}
    for label, mask in masks.items():
        dates = x.index[mask]
        report["partitions"][label] = {"start": str(dates.min().date()), "end": str(dates.max().date()), "n": int(mask.sum())}
        report["missing_features"][label] = x.loc[mask].isna().mean().to_dict()
    tr, va, te = (masks[k] for k in ("train", "validation", "test"))
    report["validation"]["persistence"] = metrics(y.loc[va], x.loc[va, baseline_column])
    fitted = {}
    for name, (kind, columns) in specs.items():
        model = make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            StandardScaler(),
            Ridge(alpha=10) if kind == "ridge" else HistGradientBoostingRegressor(
                max_iter=150, max_leaf_nodes=15, l2_regularization=5,
                early_stopping=False, random_state=settings.random_state),
        )
        model.fit(x.loc[tr, columns], y.loc[tr])
        fitted[name] = model
        report["validation"][name] = metrics(y.loc[va], model.predict(x.loc[va, columns]).clip(min=0))
    # La persistencia también puede ganar: se despliega un estimador sklearn equivalente.
    winner = min(report["validation"], key=lambda n: report["validation"][n]["mae"])
    if winner == "persistence":
        from no2_madrid.models import PersistenceRegressor
        model = PersistenceRegressor()
        columns = [baseline_column]
    else:
        model = fitted[winner]
        columns = specs[winner][1]
    development = tr | va
    model.fit(x.loc[development, columns], y.loc[development])
    prediction = np.asarray(model.predict(x.loc[te, columns])).reshape(-1)
    prediction = prediction.clip(min=0)
    candidate_predictions = {}
    for name, (_, candidate_columns) in specs.items():
        candidate = fitted[name]
        if name != winner:
            candidate.fit(x.loc[development, candidate_columns], y.loc[development])
        candidate_predictions[name] = candidate.predict(x.loc[te, candidate_columns]).clip(min=0)
    report["test"]["candidates"] = {name: metrics(y.loc[te], values)
                                       for name, values in candidate_predictions.items()}
    report["traffic_evaluation"] = traffic_evaluation(x, y, masks, report, candidate_predictions)
    report["selected"] = winner
    report["test"]["selected"] = metrics(y.loc[te], prediction)
    report["test"]["persistence"] = metrics(y.loc[te], x.loc[te, baseline_column])
    report["test"]["mae_improvement_vs_persistence"] = report["test"]["persistence"]["mae"] - report["test"]["selected"]["mae"]
    evaluation = pd.DataFrame({"observed": y.loc[te], "predicted": prediction,
                               "persistence": x.loc[te, baseline_column]})
    for name, values in candidate_predictions.items():
        evaluation[name] = values
    report["test"]["by_month"] = {str(month): metrics(g.observed, g.predicted)
                                       for month, g in evaluation.groupby(evaluation.index.strftime("%Y-%m"))}
    threshold = float(y.loc[development].quantile(.9))
    high = evaluation.loc[evaluation.observed.ge(threshold)]
    report["test"]["high_concentration"] = {"threshold_training_p90": threshold,
        "metrics": metrics(high.observed, high.predicted) if len(high) else None}
    dataset_meta = json.loads(settings.dataset_path.with_suffix(".json").read_text(encoding="utf-8"))
    report["scope"] = "Madrid"
    report["target_definition"] = dataset_meta["target_definition"]
    report["n_stations"] = len(dataset_meta["no2_stations"])
    metadata = {"created_utc": datetime.now(timezone.utc).isoformat(), "contract": data_contract(settings),
                "dataset_sha256": sha256(settings.dataset_path), "features": columns,
                "trained_through": str(x.index[development].max().date()),
                "selected": winner, "random_state": settings.random_state,
                "sklearn_version": sklearn.__version__, "pandas_version": pd.__version__,
                "no2_stations": dataset_meta["no2_stations"], "target_definition": dataset_meta["target_definition"], "test_metrics": report["test"]["selected"]}
    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    temp = settings.model_path.with_suffix(".tmp")
    try:
        joblib.dump({"model": model, "metadata": metadata}, temp)
        temp.replace(settings.model_path)
    finally:
        temp.unlink(missing_ok=True)
    write_json(settings.model_path.with_suffix(".json"), metadata)
    folder = settings.output_dir / "reports"
    write_json(folder / "metrics.json", report)
    write_json(folder / "traffic_evaluation.json", report["traffic_evaluation"])
    evaluation.to_csv(folder / "test_predictions.csv", sep=";", index_label="FECHA")
    from no2_madrid.reporting import training_report
    training_report(folder, report, evaluation)
    log.info("Modelo seleccionado: %s; MAE test %.3f µg/m³", winner, report["test"]["selected"]["mae"])
    return report


def traffic_evaluation(x, y, masks, report, predictions):
    """Comparación con parámetros y fechas idénticos; no selecciona con test."""
    import hashlib
    test_dates = [str(day.date()) for day in x.index[masks["test"]]]
    result = {"unit": "µg/m³", "same_dates": True,
              "test_dates_sha256": hashlib.sha256("\n".join(test_dates).encode()).hexdigest(),
              "test_dates": test_dates,
              "selection_rule": "Menor MAE de validación; nunca por el resultado de test",
              "interpretation": "Comparación exploratoria: 2026 ya se había consultado; no es una evaluación externa nueva ni prueba causal",
              "pairs": {}, "coverage": {}}
    primary = next((c for c in x if c.startswith("TRAFICO_INTENSIDAD_lag_")), None)
    for label, mask in masks.items():
        n = int(mask.sum())
        available = int(x.loc[mask, primary].notna().sum()) if primary else 0
        result["coverage"][label] = {"days": n, "days_with_traffic": available,
            "fraction_days_with_traffic": available/n if n else 0}
    for kind in ("ridge", "hist"):
        without, with_traffic = f"{kind}_no_traffic", f"{kind}_full"
        pair = {"without_traffic": without, "with_traffic": with_traffic}
        for split, source in (("validation", report["validation"]), ("test", report["test"]["candidates"])):
            base, enriched = source[without], source[with_traffic]
            improvement = base["mae"] - enriched["mae"]
            pair[split] = {"without_traffic": base, "with_traffic": enriched,
                "mae_improvement": improvement,
                "mae_improvement_percent": 100*improvement/base["mae"] if base["mae"] else None,
                "rmse_improvement": base["rmse"]-enriched["rmse"]}
        pair["test_by_month"] = {}
        for month in sorted(set(day.strftime("%Y-%m") for day in x.index[masks["test"]])):
            month_mask = x.index[masks["test"]].strftime("%Y-%m") == month
            observed = y.loc[masks["test"]].iloc[month_mask]
            a, b = predictions[without][month_mask], predictions[with_traffic][month_mask]
            pair["test_by_month"][month] = {"without_traffic": metrics(observed, a), "with_traffic": metrics(observed, b)}
        result["pairs"][kind] = pair
    return result
