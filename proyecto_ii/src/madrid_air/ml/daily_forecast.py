"""Pronóstico directo: un Random Forest por horizonte, sin observaciones futuras.

    1. Evaluar en varias fechas pasadas con solo los datos conocidos entonces.
    2. Reentrenar con todas las parejas origen/objetivo disponibles.
    3. Predecir las próximas 30 fechas del calendario solicitado.
"""
import json
import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

from madrid_air.processing.daily import daily_no2
from madrid_air.storage import atomic_path, read_csv, write_csv

LOG = logging.getLogger(__name__)
MIN_TRAIN_ROWS = 180


def history_features(daily):
    """Cada fila contiene solo información de esa fecha y de fechas anteriores."""
    features = pd.DataFrame(index=daily.index)
    features["no2"] = daily.no2
    for days in [1, 7, 14, 28]:
        features[f"no2_lag_{days}"] = daily.no2.shift(days)
    features["mean_7"] = daily.no2.rolling(7, min_periods=5).mean()
    features["mean_28"] = daily.no2.rolling(28, min_periods=21).mean()
    features["std_7"] = daily.no2.rolling(7, min_periods=5).std()
    features["coverage"] = daily.coverage
    return features


def horizon_features(history, calendar, horizon):
    """Añade calendario de la fecha objetivo: sí se conoce al emitir el pronóstico."""
    features = history.copy()
    target_dates = history.index + pd.Timedelta(days=horizon)
    target_calendar = calendar.reindex(target_dates)
    features["target_weekday"] = target_dates.dayofweek
    features["target_year_sin"] = np.sin(2 * np.pi * target_dates.dayofyear / 365.25)
    features["target_year_cos"] = np.cos(2 * np.pi * target_dates.dayofyear / 365.25)
    features["target_holiday"] = target_calendar.is_holiday.to_numpy()
    features["target_workday"] = target_calendar.is_workday.to_numpy()
    return features


def fit_horizon(daily, features, origin, horizon, trees):
    """Para un horizonte h, solo entrena con objetivos fechados como máximo en origin."""
    target = daily.no2.shift(-horizon)
    label_dates = daily.index + pd.Timedelta(days=horizon)
    usable = (label_dates <= origin) & target.notna() & daily.no2.notna()
    usable &= features[["mean_7", "mean_28", "target_holiday", "target_workday"]].notna().all(axis=1)
    if usable.sum() < MIN_TRAIN_ROWS:
        raise ValueError(f"Solo hay {usable.sum()} pares válidos para horizonte {horizon}; se requieren {MIN_TRAIN_ROWS}.")
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        RandomForestRegressor(n_estimators=trees, min_samples_leaf=3, random_state=42, n_jobs=-1),
    )
    model.fit(features.loc[usable], target.loc[usable])
    return model, int(usable.sum()), label_dates[usable].max()


def weekly_baseline(daily, origin, horizon):
    """Repite la última semana observada; no toma días posteriores al origen."""
    reference_date = origin - pd.Timedelta(days=6 - ((horizon - 1) % 7))
    return daily.loc[reference_date, "no2"]


def metric_table(backtest):
    """Compara modelos en las mismas filas válidas; informa también su cantidad."""
    rows = []
    for horizon, group in backtest.groupby("horizon_days"):
        common = group.dropna(subset=["actual_no2", "predicted_no2", "weekly_baseline", "persistence"])
        if common.empty:
            continue
        row = {"horizon_days": horizon, "evaluated_rows": len(common)}
        for column, prefix in [("predicted_no2", "model"), ("weekly_baseline", "weekly"), ("persistence", "persistence")]:
            errors = common[column] - common.actual_no2
            row[f"{prefix}_mae"] = float(errors.abs().mean())
            row[f"{prefix}_rmse"] = float(np.sqrt((errors**2).mean()))
        rows.append(row)
    return pd.DataFrame(rows)


def forecast(settings, days=30, folds=3, trees=100):
    """Genera CSV de 30 fechas futuras, backtest, métricas y modelos finales.

    No consulta servicios de IA. Requiere no2.csv y calendar.csv procesados.
    as_of es la fecha de emisión solicitada; origin es la última observación.
    Si hay retraso de publicación, el horizonte real supera 30 días.
    """
    if not 1 <= days <= 90 or folds < 2 or trees < 1:
        raise ValueError("Usa entre 1 y 90 días, al menos 2 cortes de evaluación y árboles positivos.")
    settings.prepare()
    start, as_of = settings.bounds
    today = pd.Timestamp.now(tz="Europe/Madrid").tz_localize(None).normalize()
    if as_of > today:
        raise ValueError("La fecha de emisión no puede estar en el futuro.")
    folder = settings.root / "data/processed"
    daily = daily_no2(read_csv(folder / "no2.csv"), start, as_of)
    calendar = pd.read_csv(folder / "calendar.csv", parse_dates=["date"]).set_index("date")
    if calendar.index.has_duplicates:
        raise ValueError("Hay fechas duplicadas en el calendario.")
    valid = daily.dropna(subset=["no2"])
    if valid.empty:
        raise ValueError("No hay días con cobertura suficiente de NO2.")
    origin = valid.index.max()
    gap = (as_of - origin).days
    if gap > 90:
        raise ValueError(f"El último NO2 válido es {origin.date()}; actualiza las descargas antes de pronosticar.")
    target_dates = pd.date_range(as_of + pd.Timedelta(days=1), periods=days)
    needed_calendar = calendar.reindex(pd.date_range(start, target_dates.max()))
    if needed_calendar[["is_holiday", "is_workday"]].isna().any().any():
        raise ValueError("El calendario no cubre todo el histórico y el periodo futuro.")
    daily = daily.loc[:origin]
    history = history_features(daily)
    if history.loc[origin, ["mean_7", "mean_28"]].isna().any():
        raise ValueError("No hay suficientes observaciones recientes para las medias móviles.")
    horizons = list(range(gap + 1, gap + days + 1))
    # Ventanas no solapadas; cada origen deja todos sus objetivos dentro del histórico.
    backtest_origins = [origin - pd.Timedelta(days=max(horizons) + days * i) for i in range(folds)]
    for date in backtest_origins:
        if date not in history.index or history.loc[date, ["no2", "mean_7", "mean_28"]].isna().any():
            raise ValueError(f"Falta historia suficiente en el corte {date.date()}; amplía el histórico o reduce --folds.")

    all_predictions, backtest_rows, models = [], [], {}
    for horizon in horizons:
        LOG.info("Evaluando y entrenando horizonte de %d días", horizon)
        features = horizon_features(history, calendar, horizon)
        for cutoff in sorted(backtest_origins):
            model, count, last_label = fit_horizon(daily, features, cutoff, horizon, trees)
            target_date = cutoff + pd.Timedelta(days=horizon)
            predicted = float(model.predict(features.loc[[cutoff]])[0])
            backtest_rows.append({
                "origin_date": cutoff, "target_date": target_date, "horizon_days": horizon,
                "actual_no2": daily.loc[target_date, "no2"], "predicted_no2": predicted,
                "weekly_baseline": weekly_baseline(daily, cutoff, horizon),
                "persistence": daily.loc[cutoff, "no2"],
                "train_rows": count, "last_training_target": last_label,
            })
        # Modelo de producción: ahora sí usa todo el histórico etiquetado disponible.
        model, count, last_label = fit_horizon(daily, features, origin, horizon, trees)
        models[horizon] = model
        all_predictions.append({
            "issued_date": as_of, "last_observation_date": origin,
            "date": origin + pd.Timedelta(days=horizon), "horizon_days": horizon,
            "predicted_no2": float(model.predict(features.loc[[origin]])[0]),
            "weekly_baseline": weekly_baseline(daily, origin, horizon),
            "train_rows": count, "last_training_target": last_label,
        })
    predictions = pd.DataFrame(all_predictions)
    backtest = pd.DataFrame(backtest_rows)
    backtest["error"] = backtest.predicted_no2 - backtest.actual_no2
    metrics = metric_table(backtest)
    if metrics.empty:
        raise ValueError("No hay objetivos válidos para evaluar el pronóstico.")
    output = settings.root / "data/final"
    # Una interpretación anterior no debe parecer asociada a nuevas predicciones.
    (output / "forecast_report.md").unlink(missing_ok=True)
    (output / "forecast_interpretation.json").unlink(missing_ok=True)
    write_csv(daily.reset_index(), output / "daily_dataset.csv")
    write_csv(predictions, output / "forecast.csv")
    write_csv(backtest, output / "daily_backtest.csv")
    write_csv(metrics, output / "daily_metrics.csv")
    with atomic_path(settings.root / "models/daily_random_forests.joblib") as path:
        joblib.dump({"models": models, "origin_date": origin, "issued_date": as_of,
                     "features": list(features.columns), "horizons": horizons}, path)
    metadata = {
        "issued_date": str(as_of.date()), "last_observation_date": str(origin.date()),
        "data_delay_days": gap, "days": days, "folds": folds,
        "backtest_origins": [str(date.date()) for date in sorted(backtest_origins)],
        "historical_days": len(daily), "valid_days": int(daily.no2.notna().sum()),
        "units": "microgramos/m3", "features_sources": ["no2", "calendar"],
    }
    with atomic_path(output / "forecast_metadata.json") as path:
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_report(output, daily, predictions, backtest, metrics, metadata)
    return predictions


def write_report(output, daily, predictions, backtest, metrics, metadata):
    """Gráfico exportable y explicación basada en cifras, sin llamadas remotas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 5))
    recent = daily.tail(60)
    ax.plot(recent.index, recent.no2, label="Media diaria observada")
    ax.plot(predictions.date, predictions.predicted_no2, "o-", markersize=3, label="Pronóstico")
    ax.plot(predictions.date, predictions.weekly_baseline, "--", label="Repetir última semana")
    ax.set(ylabel="NO2 (microgramos/m³)", title="Madrid Air: pronóstico de la media diaria")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    with atomic_path(output / "forecast.png") as path:
        fig.savefig(path, format="png", dpi=150)
    plt.close(fig)
    comparable = backtest.dropna(subset=["actual_no2", "predicted_no2", "weekly_baseline"])
    mae = (comparable.predicted_no2 - comparable.actual_no2).abs().mean()
    baseline_mae = (comparable.weekly_baseline - comparable.actual_no2).abs().mean()
    comparison = (
        "El bosque mejora la referencia semanal en esta evaluación. "
        if mae < baseline_mae else
        "El bosque no mejora la referencia semanal en esta evaluación. "
    )
    report = (
        "# Pronóstico diario de Madrid Air\n\n"
        f"Emisión: {metadata['issued_date']}. Último dato válido: {metadata['last_observation_date']}. "
        f"Retraso: {metadata['data_delay_days']} días.\n\n"
        f"Se pronostican {metadata['days']} fechas futuras, con un modelo por horizonte. "
        "No se utilizan valores futuros de NO2, tráfico o meteorología.\n\n"
        f"Evaluación en {metadata['folds']} orígenes históricos: MAE {mae:.2f}, "
        f"frente a {baseline_mae:.2f} de repetir la última semana (microgramos/m³). "
        f"{comparison}"
        "Los errores por horizonte y sus tamaños de muestra están en daily_metrics.csv. "
        "Pocos cortes producen estimaciones inestables; estos errores no son intervalos de confianza.\n\n"
        "Los modelos finales se reentrenan con todo el histórico etiquetado disponible. "
        "La evaluación usa archivos históricos revisados, no un registro exacto de su "
        "disponibilidad en cada fecha. El gráfico no representa intervalos de incertidumbre.\n"
    )
    with atomic_path(output / "forecast_summary.md") as path:
        path.write_text(report, encoding="utf-8")
