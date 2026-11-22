"""Integración diaria; nunca imputa la variable objetivo."""
from dataclasses import asdict
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from no2_madrid.config import Settings
from no2_madrid.io import sha256, write_json
from no2_madrid.preprocess.common import comprobar_claves, guardar_csv

log = logging.getLogger(__name__)


def data_contract(settings: Settings):
    """El objetivo municipal forma parte del contrato y exige reentrenamiento."""
    return {"target_scope": "madrid_network_mean", "target_version": 2,
            "meteo_source": "municipal_network", "traffic_scope": "municipal_network",
            "min_station_coverage": settings.min_station_coverage,
            "meteo_lag_days": settings.meteo_lag_days,
            "no2_lag_days": settings.no2_lag_days,
            "traffic_lag_days": settings.traffic_lag_days,
            "use_traffic": settings.use_traffic}


def read_many(paths):
    paths = list(paths)
    if not paths:
        raise FileNotFoundError("No hay datos procesados para la fuente solicitada.")
    frames = [pd.read_csv(p, sep=";", parse_dates=["FECHA"]) for p in paths]
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def aggregate_no2(frame, min_coverage=0.75):
    """Media no ponderada de estaciones válidas; jamás imputa el objetivo."""
    comprobar_claves(frame, ["FECHA", "ESTACION"])
    frame = frame.copy()
    stations = sorted(int(s) for s in frame.ESTACION.unique())
    if not stations:
        raise ValueError("No hay estaciones de NO₂ en el histórico.")
    valid = frame.VALIDO.eq(1) & frame.NO2.ge(0) & np.isfinite(frame.NO2)
    frame["NO2"] = frame.NO2.where(valid)
    grouped = frame.groupby("FECHA").NO2
    daily = grouped.agg(NO2="mean", NO2_N_ESTACIONES="count")
    daily["NO2_COBERTURA"] = daily.NO2_N_ESTACIONES / len(stations)
    daily["NO2"] = daily.NO2.where(daily.NO2_COBERTURA.ge(min_coverage))
    return daily, stations


def aggregate_traffic(paths, chunksize=250_000):
    """Toda la red, con memoria acotada a un mes y mismo peso por sensor."""
    values = ["INTENSIDAD", "OCUPACION", "CARGA", "VELOCIDAD_MEDIA"]
    results = []
    for path in paths:
        log.info("Agregando tráfico de Madrid: %s", path.name)
        sums = counts = intervals = None
        for chunk in pd.read_csv(path, sep=";", chunksize=chunksize,
                                 usecols=["FECHA_HORA", "ID_SENSOR", "TIPO_ELEMENTO", *values]):
            chunk["FECHA"] = pd.to_datetime(chunk.FECHA_HORA).dt.normalize()
            grouped = chunk.groupby(["FECHA", "ID_SENSOR", "TIPO_ELEMENTO"])
            part_sum, part_count, part_n = grouped[values].sum(), grouped[values].count(), grouped.size()
            sums = part_sum if sums is None else sums.add(part_sum, fill_value=0)
            counts = part_count if counts is None else counts.add(part_count, fill_value=0)
            intervals = part_n if intervals is None else intervals.add(part_n, fill_value=0)
        if sums is None:
            continue
        means = sums / counts.replace(0, np.nan)
        # Agregación en dos niveles: intervalos -> sensor/día -> Madrid/día.
        result = means.groupby(level="FECHA").mean().add_prefix("TRAFICO_")
        result["TRAFICO_N_SENSORES"] = means.INTENSIDAD.notna().groupby(level="FECHA").sum()
        result["TRAFICO_N_INTERVALOS"] = intervals.groupby(level="FECHA").sum()
        # Separar red urbana y vías rápidas evita mezclar sus escalas en todas las entradas.
        for kind in ("URB", "C30"):
            if kind in means.index.get_level_values("TIPO_ELEMENTO"):
                part = means.xs(kind, level="TIPO_ELEMENTO").groupby(level="FECHA").mean()
                result = result.join(part.add_prefix(f"TRAFICO_{kind}_"))
        results.append(result)
    if not results:
        raise ValueError("No hay observaciones de tráfico procesadas.")
    combined = pd.concat(results).sort_index()
    if combined.index.has_duplicates:
        raise ValueError("Los archivos de tráfico se solapan en fechas; revisa la partición mensual.")
    return combined


def aggregate_municipal_meteo(frame):
    frame = frame.copy()
    if frame.empty:
        raise ValueError("No hay observaciones meteorológicas municipales.")
    comprobar_claves(frame, ["FECHA", "ESTACION", "PARAMETRO"])
    hours = [f"H{h:02}" for h in range(1, 25)]
    # No se agregan magnitudes con menos de 18 horas válidas.
    frame["value"] = frame[hours].mean(axis=1).where(frame.N_HORAS_VALIDAS.ge(18))
    rain = frame.PARAMETRO.eq("precipitacion")
    frame.loc[rain, "value"] = frame.loc[rain, hours].sum(axis=1, min_count=18)
    frame = frame.loc[~frame.PARAMETRO.eq("direccion_viento")]
    result = frame.groupby(["FECHA", "PARAMETRO"]).value.mean().unstack("PARAMETRO").add_prefix("METEO_")
    for name, agg in [("METEO_temperatura_min", "min"), ("METEO_temperatura_max", "max")]:
        temp = frame.loc[frame.PARAMETRO.eq("temperatura")]
        per_station = pd.Series(getattr(temp[hours], agg)(axis=1).where(temp.N_HORAS_VALIDAS.ge(18)).to_numpy(), index=temp.FECHA)
        result[name] = per_station.groupby(level=0).mean()
    result["METEO_N_ESTACIONES"] = frame.loc[frame.value.notna()].groupby("FECHA").ESTACION.nunique()
    result["METEO_HORAS_VALIDAS"] = frame.groupby("FECHA").N_HORAS_VALIDAS.mean()
    return result


def build_dataset(settings: Settings):
    p = settings.process_dir
    files = sorted((p / "no2").glob("calidad_aire_diario_*.csv"))
    no2 = read_many(files)
    aggregated, no2_stations = aggregate_no2(no2, settings.min_station_coverage)
    index = pd.date_range(aggregated.index.min(), aggregated.index.max() + pd.Timedelta(days=1), name="FECHA")
    daily = aggregated.reindex(index)
    meteo_files = sorted((p / "meteorologia_municipal").glob("meteorologicos_horarios_*.csv"))
    meteo = aggregate_municipal_meteo(read_many(meteo_files))
    daily = daily.join(meteo)
    calendar_path = p / "calendar" / "calendario_laboral.csv"
    calendar = read_many([calendar_path])
    comprobar_claves(calendar, ["FECHA"])
    daily = daily.join(calendar.set_index("FECHA")[["TIPO_DIA"]])
    traffic_files = []
    if settings.use_traffic:
        traffic_files = sorted((p / "traffic").glob("trafico_*.csv.gz"))
        # Caché de toda la red por firma de archivos; evita releer gigabytes al predecir.
        cache = settings.data_dir / "dataset" / "traffic_daily.csv"
        signature = {"version": 2, "scope": "madrid_network", "files": [
            [str(f), f.stat().st_size, f.stat().st_mtime_ns] for f in traffic_files]}
        import json
        meta = cache.with_suffix(".json")
        if cache.exists() and meta.exists() and json.loads(meta.read_text(encoding="utf-8")) == signature:
            traffic = pd.read_csv(cache, sep=";", parse_dates=["FECHA"]).set_index("FECHA")
        else:
            traffic = aggregate_traffic(traffic_files)
            guardar_csv(traffic.reset_index(), cache)
            write_json(meta, signature)
        daily = daily.join(traffic)
    guardar_csv(daily.reset_index(), settings.dataset_path)
    sources = [*files, *meteo_files, calendar_path, *traffic_files]
    report = {
        "contract": data_contract(settings), "no2_stations": no2_stations,
        "target_definition": "Media aritmética diaria de estaciones válidas de la red municipal de Madrid",
        "n_no2_stations": len(no2_stations),
        "rows": len(daily), "start": str(index.min().date()), "end": str(index.max().date()),
        "target_valid": int(daily.NO2.notna().sum()),
        "missing_by_column": daily.isna().sum().to_dict(),
        "missing_target_dates": [str(d.date()) for d in daily.index[daily.NO2.isna()]],
        "dataset_sha256": sha256(settings.dataset_path),
        "sources": [{"path": str(f), "bytes": f.stat().st_size, "mtime_ns": f.stat().st_mtime_ns} for f in sources],
    }
    write_json(settings.dataset_path.with_suffix(".json"), report)
    log.info("Dataset: %d días, %d objetivos válidos", len(daily), report["target_valid"])
    return daily
