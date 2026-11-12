"""Prepara datos verificables para la IA y guarda el informe como CSV."""
from pathlib import Path

import joblib
import pandas as pd

from madrid_air.ai.client import ResultsClient, ResultsContext
from madrid_air.storage import write_csv


def interpret_prediction(root: Path, prediction: pd.DataFrame, client: ResultsClient) -> pd.DataFrame:
    """Une una predicción con las métricas del modelo guardado y genera su texto.

    Leemos las métricas del propio joblib para usar las del modelo, incluso si
    metrics.json se ha perdido. No se envían el dataset ni las credenciales.
    """
    artifact = joblib.load(root / "models/random_forest.joblib")
    metrics = artifact["metrics"]
    row = prediction.iloc[0]
    results = ResultsContext(
        timestamp=str(row.timestamp), target_timestamp=str(row.target_timestamp),
        predicted_no2=float(row.predicted_no2),
        mae=float(metrics["mae"]), rmse=float(metrics["rmse"]),
        baseline_mae=float(metrics["baseline_mae"]),
        baseline_rmse=float(metrics["baseline_rmse"]),
        test_start=metrics["test_start"], test_end=metrics["test_end"],
        test_rows=int(metrics["test_rows"]),
    )
    interpretation = client.interpret(results)
    report = prediction.copy()
    for name in ["mae", "rmse", "baseline_mae", "baseline_rmse", "test_start", "test_end", "test_rows"]:
        report[name] = metrics[name]
    report["mae_comparison"] = results.mae_comparison
    report["interpretation"] = interpretation.text
    report["ai_mode"] = interpretation.mode
    report["ai_provider"] = interpretation.provider
    report["ai_model"] = interpretation.model
    write_csv(report, root / "data/final/analysis.csv")
    return report
