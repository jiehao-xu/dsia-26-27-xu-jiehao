from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from no2_madrid.clients.base import PredictionContext
from no2_madrid.clients.mock import MockClient
from no2_madrid.config import Settings
from no2_madrid.dataset import aggregate_traffic, build_dataset, aggregate_no2
from no2_madrid.demo import make_demo
from no2_madrid.features import make_features
from no2_madrid.ingestion.metadata import normalize
from no2_madrid.predict import predict
from no2_madrid.train import train


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", output_dir=tmp_path, use_traffic=False)


def test_lags_are_calendar_days_and_ignore_future(settings):
    dates = pd.date_range("2025-01-01", periods=20)
    daily = pd.DataFrame({"NO2": np.arange(20.), "TIPO_DIA": "laborable",
                          "METEO_temperatura": np.arange(20.)*2}, index=dates)
    x = make_features(daily.drop(index=dates[7]), settings)
    assert pd.isna(x.loc[dates[8], "no2_lag_1"])
    assert x.loc[dates[10], "METEO_temperatura_lag_7"] == 6
    changed = daily.copy()
    changed.loc[dates[10]:, ["NO2", "METEO_temperatura"]] = 9999
    pd.testing.assert_frame_equal(make_features(daily, settings).loc[:dates[10]],
                                  make_features(changed, settings).loc[:dates[10]])


def test_city_target_uses_multiple_stations_and_minimum_coverage():
    frame = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-01"]*3+["2025-01-02"]*3),
                          "ESTACION": [4, 8, 11]*2, "NO2": [10., 30., 50., 10., 999., 999.],
                          "VALIDO": [1, 1, 1, 1, 0, 0]})
    daily, stations = aggregate_no2(frame, .75)
    assert stations == [4, 8, 11]
    assert daily.iloc[0].NO2 == 30
    assert daily.iloc[0].NO2_N_ESTACIONES == 3
    assert pd.isna(daily.iloc[1].NO2)
    assert daily.iloc[1].NO2_COBERTURA == pytest.approx(1/3)


def test_traffic_chunk_independence_and_equal_sensor_weight(tmp_path):
    frame = pd.DataFrame({"FECHA_HORA": ["2025-01-01 00:15:00"]*4,
                          "ID_SENSOR": [1, 1, 1, 2], "TIPO_ELEMENTO": "URB", "INTENSIDAD": [10, 20, 30, 100],
                          "OCUPACION": [10]*4, "CARGA": [20]*4, "VELOCIDAD_MEDIA": [np.nan]*4})
    path = tmp_path / "traffic.csv.gz"
    frame.to_csv(path, sep=";", index=False)
    a = aggregate_traffic([path], chunksize=1)
    b = aggregate_traffic([path], chunksize=10)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)
    assert a.iloc[0].TRAFICO_INTENSIDAD == 60
    assert a.iloc[0].TRAFICO_N_SENSORES == 2
    assert a.iloc[0].TRAFICO_URB_INTENSIDAD == 60



def test_metadata_normalization():
    frame = pd.DataFrame({"CODIGO": [28079004], "LATITUD": ["40,42"], "LONGITUD": ["-3,71"]})
    result = normalize(frame, "air")
    assert result.iloc[0].ESTACION == 4
    assert result.iloc[0].LONGITUD == -3.71


def test_mock_never_uses_credentials():
    context = PredictionContext("2026-01-02", "Madrid", 30, 2, 5)
    assert MockClient().explain(context) == MockClient().explain(context)
    assert "30.00" in MockClient().explain(context)


def test_google_sdk_contract_without_network(monkeypatch):
    from google import genai
    from no2_madrid.clients.google import GoogleClient
    from types import SimpleNamespace
    calls = {}

    class FakeSDK:
        def __init__(self, **kwargs):
            calls["options"] = kwargs["http_options"]
            self.models = self

        def generate_content(self, **kwargs):
            calls["request"] = kwargs
            return SimpleNamespace(text="Resumen de prueba.")

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(genai, "Client", FakeSDK)
    client = GoogleClient("test-key", "test-model")
    assert client.explain(PredictionContext("2026-01-02", "Madrid", 30, 0, 5)) == "Resumen de prueba."
    assert calls["request"]["model"] == "test-model"
    assert calls["options"].timeout == 20_000
    assert calls["options"].retry_options.attempts == 2
    assert calls["closed"]
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GoogleClient("", "test-model")



def test_settings_validate_delays_and_hide_keys():
    with pytest.raises(ValueError):
        Settings(meteo_lag_days=0)
    assert "secret" not in repr(Settings(google_api_key="secret"))


@pytest.mark.integration
def test_train_save_load_predict_and_provider_failure(settings):
    settings = replace(settings, use_traffic=True)
    make_demo(settings)
    dates = pd.date_range("2023-01-01", "2026-03-31")
    traffic = pd.DataFrame({"FECHA_HORA": dates + pd.Timedelta(hours=12), "ID_SENSOR": 1, "TIPO_ELEMENTO": "URB",
                            "INTENSIDAD": 100., "OCUPACION": 10., "CARGA": 20., "VELOCIDAD_MEDIA": np.nan})
    traffic_dir = settings.process_dir / "traffic"
    traffic_dir.mkdir(parents=True)
    traffic.to_csv(traffic_dir / "trafico_demo.csv.gz", sep=";", index=False)
    daily = build_dataset(settings)
    assert len(daily) > 1000
    report = train(settings)
    assert report["partitions"]["test"]["start"] > "2025-12-31"
    assert np.isfinite(report["test"]["selected"]["mae"])
    assert report["traffic_evaluation"]["same_dates"] is True
    for pair in report["traffic_evaluation"]["pairs"].values():
        assert pair["test"]["without_traffic"]["n"] == pair["test"]["with_traffic"]["n"]
        assert pair["test"]["mae_improvement"] == pytest.approx(
            pair["test"]["without_traffic"]["mae"]-pair["test"]["with_traffic"]["mae"])
    assert report["selected"] == min(report["validation"], key=lambda k: report["validation"][k]["mae"])
    assert (settings.output_dir / "reports/traffic_evaluation.md").exists()
    artifact = joblib.load(settings.model_path)
    assert hasattr(artifact["model"], "predict")
    first = predict(settings, "2026-03-01")
    assert first["no2"] == predict(settings, "2026-03-01")["no2"]
    assert first["ai_status"] == "mock"
    assert first["scope"] == "Madrid"
    assert "station" not in first
    assert first["network_station_count"] == 2
    assert first["input_no2_coverage"]["valid_stations"] == 2
    assert first["information_cutoffs"]["meteo"] == "2026-02-22"

    class FailingClient:
        def explain(self, context):
            raise TimeoutError("sensitive-error-content")

    fallback = predict(settings, "2026-03-01", client=FailingClient())
    assert fallback["no2"] == first["no2"]
    assert fallback["ai_status"] == "fallback"
    assert "sensitive" not in json.dumps(fallback)
    with pytest.raises(ValueError, match="posterior"):
        predict(settings, "2024-03-01")
    with pytest.raises(ValueError, match="configuración"):
        predict(replace(settings, meteo_lag_days=2), "2026-03-01")
    with pytest.raises(ValueError, match="fuera"):
        predict(settings, "2027-01-01")
    # Cambiar el test no puede cambiar el estimador ni el ganador de validación.
    previous = artifact["model"].predict(pd.DataFrame([[30.]*len(artifact["metadata"]["features"])], columns=artifact["metadata"]["features"]))
    path = settings.process_dir / "no2" / "calidad_aire_diario_2026.csv"
    frame = pd.read_csv(path, sep=";")
    frame["NO2"] += 100
    frame.to_csv(path, sep=";", index=False)
    build_dataset(settings)
    changed_report = train(settings)
    changed_artifact = joblib.load(settings.model_path)
    assert changed_report["selected"] == report["selected"]
    np.testing.assert_allclose(previous, changed_artifact["model"].predict(pd.DataFrame([[30.]*len(artifact["metadata"]["features"])], columns=artifact["metadata"]["features"])))


def test_cli_help_and_errors():
    result = subprocess.run([sys.executable, "-m", "no2_madrid", "--help"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0
    assert "build-dataset" in result.stdout


def test_municipal_meteo_coverage_and_aggregation():
    from no2_madrid.dataset import aggregate_municipal_meteo
    rows = []
    for parameter, hours_valid in [("temperatura", 18), ("precipitacion", 18), ("humedad_relativa", 17)]:
        row = {"FECHA": pd.Timestamp("2024-01-01"), "ESTACION": 4,
               "PARAMETRO": parameter, "N_HORAS_VALIDAS": hours_valid}
        row.update({f"H{hour:02}": (-2. if parameter == "temperatura" else 1.) if hour <= hours_valid else np.nan
                    for hour in range(1, 25)})
        rows.append(row)
    aggregated = aggregate_municipal_meteo(pd.DataFrame(rows)).iloc[0]
    assert aggregated.METEO_temperatura == -2
    assert aggregated.METEO_precipitacion == 18
    assert pd.isna(aggregated.METEO_humedad_relativa)


def test_municipal_configuration_defaults():
    from no2_madrid.cli import parser
    assert Settings().data_dir == Path("data")
    args = parser().parse_args(["ingest", "--source", "municipal"])
    assert args.source == "municipal"
    assert Settings().meteo_lag_days == 7


def test_city_meteo_averages_stations_equally():
    from no2_madrid.dataset import aggregate_municipal_meteo
    rows = []
    for station, value in [(4, 10.), (8, 20.)]:
        row = {"FECHA": pd.Timestamp("2024-01-01"), "ESTACION": station,
               "PARAMETRO": "temperatura", "N_HORAS_VALIDAS": 24}
        row.update({f"H{hour:02}": value for hour in range(1, 25)})
        rows.append(row)
    daily = aggregate_municipal_meteo(pd.DataFrame(rows))
    assert daily.iloc[0].METEO_temperatura == 15
    assert daily.iloc[0].METEO_N_ESTACIONES == 2


def test_city_coverage_configuration():
    with pytest.raises(ValueError, match="MIN_STATION_COVERAGE"):
        Settings(min_station_coverage=0)
    assert Settings().min_station_coverage == .75


def test_city_target_accepts_exactly_75_percent_and_excludes_invalid_values():
    frame = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-01"]*4+["2025-01-02"]*4),
                          "ESTACION": [4, 8, 11, 16]*2,
                          "NO2": [0., 10., 20., 999., 0., 10., 20., 999.],
                          "VALIDO": [1, 1, 1, 0, 0, 1, 1, 0]})
    daily, stations = aggregate_no2(frame, .75)
    assert len(stations) == 4
    assert daily.iloc[0].NO2 == 10
    assert daily.iloc[0].NO2_COBERTURA == .75
    assert pd.isna(daily.iloc[1].NO2)


def test_city_target_rejects_conflicting_station_day():
    frame = pd.DataFrame({"FECHA": pd.to_datetime(["2025-01-01"]*2),
                          "ESTACION": [4, 4], "NO2": [10., 20.], "VALIDO": [1, 1]})
    with pytest.raises(ValueError, match="misma clave"):
        aggregate_no2(frame)

def test_incremental_traffic_cache_only_reads_new_months(tmp_path, monkeypatch):
    from no2_madrid import dataset
    files = []
    for month in (1, 2):
        file = tmp_path / f"trafico_2026_{month:02}.csv.gz"
        pd.DataFrame({"FECHA_HORA": [f"2026-{month:02}-01 12:00:00"], "ID_SENSOR": [1],
                      "TIPO_ELEMENTO": ["URB"], "INTENSIDAD": [100.*month], "OCUPACION": [10.],
                      "CARGA": [20.], "VELOCIDAD_MEDIA": [np.nan]}).to_csv(file, sep=";", index=False)
        files.append(file)
    cache = tmp_path / "daily.csv"
    dataset.load_traffic_daily(files[:1], cache)
    original = dataset.aggregate_traffic
    calls = []
    def tracked(paths, **kwargs):
        calls.extend(paths)
        return original(paths, **kwargs)
    monkeypatch.setattr(dataset, "aggregate_traffic", tracked)
    incremental = dataset.load_traffic_daily(files, cache)
    assert calls == [files[1]]
    expected = original(files)
    pd.testing.assert_frame_equal(incremental, expected, check_dtype=False)
    calls.clear()
    dataset.load_traffic_daily(files, cache)
    assert calls == []
    # Si cambia un original ya agregado, se invalida toda la caché.
    files[0].write_bytes(files[0].read_bytes())
    import os
    stat = files[0].stat()
    os.utime(files[0], ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    dataset.load_traffic_daily(files, cache)
    assert calls == files
