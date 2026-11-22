"""Inferencia real con un paquete pequeño, sin ingesta ni entrenamiento."""
from dataclasses import fields
import json
import math
import os
from pathlib import Path

from no2_madrid.config import Settings
from no2_madrid.io import sha256, write_json
from no2_madrid.predict import predict


def quick_demo(output_dir=Path("artifacts/quick-demo"), ai_mode="mock", sample_dir=None):
    sample_dir = Path(sample_dir) if sample_dir is not None else Path(__file__).parent / "sample"
    manifest = json.loads((sample_dir / "manifest.json").read_text(encoding="utf-8"))
    expected_files = {"model.joblib", "model.json", "daily.csv", "daily.json"}
    if set(manifest["files"]) != expected_files:
        raise ValueError("El paquete de prueba rápida está incompleto.")
    # Validar la copia distribuida antes de cargar su artefacto de confianza.
    for filename, expected_hash in manifest["files"].items():
        if sha256(sample_dir / filename) != expected_hash:
            raise ValueError(f"Archivo de prueba rápida modificado: {filename}.")
    metadata = json.loads((sample_dir / "model.json").read_text(encoding="utf-8"))
    import sklearn
    import pandas
    if sklearn.__version__ != metadata["sklearn_version"] or pandas.__version__ != metadata["pandas_version"]:
        raise ValueError("Versiones incompatibles con el modelo de muestra; instala el entorno con uv sync --locked --package no2-madrid --group dev.")
    field_names = {field.name for field in fields(Settings)}
    parameters = {name: value for name, value in metadata["contract"].items() if name in field_names}
    parameters.update(output_dir=Path(output_dir), ai_mode=ai_mode)
    if ai_mode == "real":
        from dotenv import load_dotenv
        load_dotenv()
        parameters.update(google_api_key=os.getenv("GOOGLE_API_KEY", ""),
                          google_model=os.getenv("GOOGLE_MODEL", "gemini-3.1-flash-lite"))
    settings = Settings(**parameters)
    result = predict(settings, manifest["prediction_date"],
                     model_path=sample_dir / "model.joblib", dataset_path=sample_dir / "daily.csv")
    if not math.isclose(result["no2"], manifest["expected_no2"], rel_tol=1e-7, abs_tol=1e-7):
        raise ValueError("La predicción no coincide con la referencia distribuida; revisa el modelo y las variables.")
    result["quick_demo"] = {"real_data": True, "trained_model": True,
        "training_performed": False, "downloads_performed": False,
        "sample_start": manifest["sample_start"], "sample_end": manifest["sample_end"],
        "reference_prediction_matches": True}
    write_json(settings.output_dir / "reports/runs" / f"prediction_{result['date']}.json", result)
    return result
