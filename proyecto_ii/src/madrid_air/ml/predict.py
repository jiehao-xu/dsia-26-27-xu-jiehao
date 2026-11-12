import joblib
import pandas as pd

from madrid_air.storage import read_csv, write_csv


def predict(root, timestamp=None):
    """Carga el modelo y predice desde una hora observada, sin volver a entrenar.

    Si no se indica timestamp, usa la última hora con NO2. El resultado incluye
    la fecha objetivo para no confundir una predicción histórica con una actual.
    """
    model_path = root / "models/random_forest.joblib"
    dataset_path = root / "data/final/dataset.csv"
    if not dataset_path.exists():
        raise ValueError(
            f"Falta el dataset en {dataset_path}. Completa las descargas (AEMET requiere "
            "AEMET_API_KEY) y ejecuta build y train, o usa run para realizar el flujo completo. "
            "El modo mock solo simula la interpretación de Gemini, no los datos ni sklearn."
        )
    if not model_path.exists():
        raise ValueError(
            f"Falta el modelo en {model_path}. Ejecuta 'uv run --package madrid-air "
            "madrid-air train' con el mismo --root antes de predict o analyze."
        )
    artifact = joblib.load(model_path)
    frame = read_csv(dataset_path).sort_values("timestamp")
    if timestamp:
        instant = pd.Timestamp(timestamp)
        if instant.tzinfo is None:
            raise ValueError("Indica una fecha con zona horaria, por ejemplo 2023-01-31T22:00:00Z.")
        frame = frame.loc[frame.timestamp.eq(instant)]
    else:
        frame = frame.loc[frame.no2.notna()].tail(1)
    if frame.empty or frame.no2.isna().any():
        raise ValueError("No hay observación de NO2 disponible para emitir la predicción.")
    output = frame[["timestamp", "target_timestamp"]].copy()
    output["predicted_no2"] = artifact["model"].predict(frame[artifact["features"]])
    write_csv(output, root / "data/final/predictions.csv")
    return output
