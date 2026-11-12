"""Interpreta el pronóstico completo con una sola llamada al proveedor configurado."""
from dataclasses import asdict
import json

import pandas as pd

from madrid_air.ai.client import ResultsClient, Interpretation, AIServiceError
from madrid_air.storage import atomic_path, write_csv


def validate_response(text: str, dates: list[str]) -> dict:
    """Exige una explicación por fecha, sin duplicados ni fechas inventadas."""
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1])
    try:
        payload = json.loads(cleaned)
        if not isinstance(payload, dict) or not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
            raise ValueError("Resumen ausente")
        rows = payload.get("rows")
        if not isinstance(rows, list) or len(rows) != len(dates):
            raise ValueError("Cantidad de filas incorrecta")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("date"), str):
                raise ValueError("Fecha inválida")
            if not isinstance(row.get("interpretation"), str) or not row["interpretation"].strip():
                raise ValueError("Interpretación vacía")
        returned_dates = [row["date"] for row in rows]
        if len(set(returned_dates)) != len(dates) or set(returned_dates) != set(dates):
            raise ValueError("Fechas distintas a las predicciones")
    except (ValueError, TypeError):
        raise AIServiceError("La API no devolvió un resumen y una interpretación válida para cada fecha. No se guardarán resultados parciales.") from None
    return payload


def markdown_cell(value) -> str:
    """Evita que barras o saltos de línea rompan la tabla del informe."""
    return str(value).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def enrich_predictions(predictions, calendar, metrics):
    """Calcula contexto verificable en Python antes de pedir explicaciones a la IA."""
    predictions = predictions.sort_values("date").copy()
    # Recalcular estas columnas permite ejecutar forecast-analyze varias veces.
    extra_columns = ["weekday", "is_holiday", "is_workday", "difference_weekly",
                     "difference_previous_day", "evaluated_rows", "model_mae", "weekly_mae"]
    predictions = predictions.drop(columns=extra_columns, errors="ignore")
    predictions = predictions.merge(calendar[["date", "is_holiday", "is_workday"]],
                                    on="date", how="left", validate="one_to_one")
    if predictions[["is_holiday", "is_workday"]].isna().any().any():
        raise ValueError("Falta calendario para interpretar alguna fecha.")
    names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    predictions["weekday"] = pd.to_datetime(predictions.date).dt.dayofweek.map(dict(enumerate(names)))
    predictions["difference_weekly"] = predictions.predicted_no2 - predictions.weekly_baseline
    predictions["difference_previous_day"] = predictions.predicted_no2.diff()
    return predictions.merge(metrics[["horizon_days", "evaluated_rows", "model_mae", "weekly_mae"]],
                             on="horizon_days", how="left", validate="many_to_one")


def interpret_forecast(root, client: ResultsClient) -> Interpretation:
    """Lee los resultados ya calculados; permite reintentar sin entrenar de nuevo.

    Solo envía fechas, predicciones y métricas agregadas. El proveedor redacta
    la explicación; sklearn conserva la responsabilidad de predecir y evaluar.
    """
    folder = root / "data/final"
    metadata = json.loads((folder / "forecast_metadata.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(folder / "forecast.csv")
    dates = predictions.date.tolist()
    if not dates or predictions.date.isna().any() or predictions.date.duplicated().any():
        raise ValueError("El pronóstico debe contener fechas únicas y no vacías.")
    predictions = enrich_predictions(predictions,
        pd.read_csv(root / "data/processed/calendar.csv"),
        pd.read_csv(folder / "daily_metrics.csv"))
    backtest = pd.read_csv(folder / "daily_backtest.csv")
    common = backtest.dropna(subset=["actual_no2", "predicted_no2", "weekly_baseline", "persistence"])
    if common.empty:
        raise ValueError("No hay observaciones comparables para interpretar la evaluación.")
    evaluation = {"evaluated_rows": len(common)}
    for column in ["predicted_no2", "weekly_baseline", "persistence"]:
        errors = common[column] - common.actual_no2
        evaluation[column] = {"mae": round(float(errors.abs().mean()), 3),
                              "rmse": round(float((errors.pow(2).mean()) ** 0.5), 3)}
    evaluation["improves_weekly_baseline"] = evaluation["predicted_no2"]["mae"] < evaluation["weekly_baseline"]["mae"]
    facts = {
        "station": "Escuelas Aguirre, Madrid", "metadata": metadata,
        "predictions": json.loads(predictions[["date", "horizon_days", "predicted_no2",
            "weekly_baseline", "difference_weekly", "difference_previous_day", "weekday",
            "is_holiday", "is_workday", "evaluated_rows", "model_mae", "weekly_mae"]].round(3).to_json(orient="records")),
        "evaluation": evaluation,
        "baseline_definition": "La referencia semanal repite los valores de la última semana por día de la semana; NO calcula su media. Persistencia mantiene el último valor observado.",
    }
    instructions = (
        'Devuelve únicamente JSON con formato {"summary":"resumen global", '
        '"rows":[{"date":"AAAA-MM-DD","interpretation":"explicación de esa fila"}]}. '
        "Incluye exactamente una fila por cada fecha recibida, sin omitir ninguna. "
        "Cada explicación debe tener entre 45 y 75 palabras. Interpreta los datos específicos "
        "de esa fila: valor, día de semana y condición laborable/festivo, diferencia frente "
        "a la referencia semanal y cambio respecto a la predicción del día anterior. "
        "Relaciona el horizonte con su MAE histórico y evaluated_rows (tamaño de muestra); "
        "con pocas observaciones indica que la evidencia es limitada. Un null significa "
        "dato no disponible: no lo inventes. El MAE no es el error conocido de esa fecha futura. "
        "El calendario describe la fecha, no prueba la causa del valor. Usa las diferencias "
        "ya calculadas; no añadas nuevas cifras calculadas. "
        "El resumen global tendrá un máximo de 150 palabras. "
        "IMPORTANTE: metadata.folds es el número de cortes históricos. "
        "evaluation.evaluated_rows cuenta pares de predicción/observación sumados entre "
        "todos los horizontes; NO son cortes ni observaciones independientes. "
        "Explica en español este pronóstico de medias diarias "
        "de NO2. Usa solo los hechos del JSON. Resume las fechas y los valores previstos, "
        "distinguiendo predicción de medición. Explica el retraso entre emisión y última "
        "observación y el horizonte real. Explica el MAE y compara el bosque con repetir "
        "la última semana y con persistencia (mantener el último valor). No ocultes si "
        "empeora las referencias. La evaluación tiene pocos cortes históricos y usa archivos "
        "revisados. No atribuyas causas, ni inventes meteorología, tráfico, alertas sanitarias "
        "o límites legales. Los errores históricos no son intervalos de confianza. "
        "En el resumen indica expresamente que los errores no son intervalos de confianza. "
        "No llames media semanal a la referencia que repite la última semana. "
        "No afirmes que el modelo es fiable por haber completado la ejecución."
    )
    if client.mode == "mock":
        payload = {"summary": "[MOCK] Informe de prueba sin llamada a la API.", "rows": [
            {"date": row.date, "interpretation": f"[MOCK] Media prevista: {row.predicted_no2:.2f} microgramos/m3; horizonte: {row.horizon_days} días."}
            for row in predictions.itertuples()
        ]}
        result = Interpretation(json.dumps(payload, ensure_ascii=False), "mock", "local", "template-v2")
    else:
        result = client.generate(instructions, json.dumps(facts, ensure_ascii=False, allow_nan=False),
                                 max_output_tokens=700 + 220 * len(predictions))
    payload = validate_response(result.text, dates)
    by_date = {row["date"]: row["interpretation"].strip() for row in payload["rows"]}
    predictions["interpretation"] = predictions.date.map(by_date)
    predictions["ai_mode"] = result.mode
    predictions["ai_provider"] = result.provider
    predictions["ai_model"] = result.model
    table = "| Fecha | NO₂ previsto (µg/m³) | Referencia semanal (µg/m³) | Horizonte (días) | Interpretación de Gemini/IA |\n"
    table += "| --- | --- | --- | --- | --- |\n"
    visible = predictions[["date", "predicted_no2", "weekly_baseline", "horizon_days", "interpretation"]].round(2)
    for row in visible.itertuples(index=False, name=None):
        table += "| " + " | ".join(markdown_cell(value) for value in row) + " |\n"
    # Las cifras originales se conservan; el modelo remoto solo aporta texto.
    write_csv(predictions, folder / "forecast.csv")
    # Conserva la procedencia y los hechos enviados para poder revisar la explicación.
    with atomic_path(folder / "forecast_interpretation.json") as path:
        path.write_text(json.dumps({**asdict(result), "facts": facts}, ensure_ascii=False, indent=2), encoding="utf-8")
    with atomic_path(folder / "forecast_report.md") as path:
        path.write_text(
            f"# Interpretación del pronóstico diario\n\n"
            f"Emisión: {metadata['issued_date']}. Modo: {result.mode}. "
            f"Proveedor: {result.provider}. Modelo: {result.model}.\n\n"
            f"Evaluación calculada en Python: {metadata['folds']} cortes históricos; "
            f"{len(common)} pares de predicción/observación comparables entre todos los horizontes.\n\n"
            f"## Resultados e interpretación por fecha\n\n{table}\n"
            f"## Interpretación global\n\n{payload['summary']}\n",
            encoding="utf-8",
        )
    return Interpretation(payload["summary"], result.mode, result.provider, result.model)
