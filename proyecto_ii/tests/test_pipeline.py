import json
from unittest.mock import Mock
import zipfile

import numpy as np
import pandas as pd
import pytest

from madrid_air.config import Settings
from madrid_air.ingestion import aemet
from madrid_air.ingestion.common import download, municipal_files, period
from madrid_air.integration.features import add_features
from madrid_air.integration.joins import join_sources
from madrid_air.ml.predict import predict
from madrid_air.ml.train import train
from madrid_air.pipeline import build, run, update
from madrid_air.processing import clean_aemet, clean_calendar, clean_no2, clean_traffic
from madrid_air.storage import atomic_path, read_csv, upsert, write_csv


def no2_file(tmp_path, days):
    rows = []
    for day in days:
        row = dict(provincia=28, municipio=79, estacion=8, magnitud=8,
                   ano=day.year, mes=day.month, dia=day.day)
        for h in range(1, 25):
            row[f"h{h:02}"] = h
            row[f"v{h:02}"] = "V" if h != 4 else "N"
        rows.append(row)
    path = tmp_path / "air.csv"
    pd.DataFrame(rows).to_csv(path, sep=";", index=False)
    return path


def test_no2_filters_validity_and_hour_labels(tmp_path):
    path = no2_file(tmp_path, [pd.Timestamp("2023-01-01")])
    raw = pd.read_csv(path, sep=";")
    other = raw.copy()
    other["estacion"] = 4
    pd.concat([raw, other]).to_csv(path, sep=";", index=False)
    frame = clean_no2.clean(path).sort_values("timestamp")
    assert len(frame) == 24
    assert frame.iloc[0].timestamp == pd.Timestamp("2022-12-31T23:00Z")
    assert frame.iloc[-1].timestamp == pd.Timestamp("2023-01-01T22:00Z")
    assert pd.isna(frame.iloc[3].no2)


@pytest.mark.parametrize("day,expected", [("2023-03-26", 23), ("2023-10-29", 23)])
def test_dst_ambiguous_hours_not_invented(tmp_path, day, expected):
    frame = clean_no2.clean(no2_file(tmp_path, [pd.Timestamp(day)]))
    assert len(frame) == expected
    assert frame.timestamp.is_unique


def test_zip_input(tmp_path):
    source = no2_file(tmp_path, [pd.Timestamp("2023-01-01")])
    path = tmp_path / "air.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.write(source, arcname="nested/air.csv")
    assert len(clean_no2.clean(path)) == 24


def test_aemet_decimal_and_missing_fields(tmp_path):
    path = tmp_path / "weather.json"
    path.write_text(json.dumps([{"fecha": "2023-01-01", "tmed": "3,5", "prec": "Ip"}]))
    result = clean_aemet.clean(path)
    assert result.temperature.iloc[0] == 3.5
    assert result.precipitation.iloc[0] == 0
    assert result.humidity.isna().all()


def test_calendar_official_classes(tmp_path):
    path = tmp_path / "calendar.csv"
    path.write_text("Dia;laborable / festivo / domingo festivo\n01/01/2023;domingo festivo\n02/01/2023;laborable\n07/01/2023;sabado\n", encoding="utf-8")
    result = clean_calendar.clean(path)
    assert result.is_holiday.tolist() == [1, 0, 0]
    assert result.is_workday.tolist() == [0, 1, 0]


def test_traffic_mean_dedup_and_invalid(tmp_path):
    path = tmp_path / "traffic.csv"
    frame = pd.DataFrame({"id": [1, 1, 1, 1, 2],
                          "fecha": ["2023-01-01 00:00:00", "2023-01-01 00:15:00",
                                    "2023-01-01 00:15:00", "2023-01-01 01:00:00", "2023-01-01 00:00:00"],
                          "intensidad": [100, 300, 300, -1, 999], "ocupacion": [10, 30, 30, 20, 99],
                          "error": ["N", "N", "N", "E", "N"], "periodo_integracion": [5]*5})
    frame.to_csv(path, sep=";", index=False)
    result = clean_traffic.clean(path, [1])
    assert len(result) == 2
    assert result.intensity.iloc[0] == 200
    assert pd.isna(result.intensity.iloc[1])


def test_upsert_replaces_with_invalid_correction(tmp_path):
    path = tmp_path / "no2.csv"
    ts = pd.date_range("2023-01-01", periods=2, freq="h", tz="UTC")
    upsert(pd.DataFrame({"timestamp": ts, "no2": [1., 2.]}), path, ["timestamp"])
    new = pd.DataFrame({"timestamp": ts[1:], "no2": [np.nan]})
    upsert(new, path, ["timestamp"])
    upsert(new, path, ["timestamp"])
    result = read_csv(path)
    assert len(result) == 2
    assert pd.isna(result.no2.iloc[-1])


def test_atomic_failure_keeps_previous_file(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("original")
    with pytest.raises(RuntimeError):
        with atomic_path(path) as temporary:
            temporary.write_text("incomplete")
            raise RuntimeError("simulated write failure")
    assert path.read_text() == "original"
    assert list(tmp_path.glob("*.tmp")) == []


def source_frames(start="2023-01-01", days=14):
    timestamps = pd.date_range(pd.Timestamp(start).tz_localize("Europe/Madrid"), periods=days*24,
                               freq="h").tz_convert("UTC")
    dates = pd.date_range(start, periods=days)
    no2 = pd.DataFrame({"timestamp": timestamps, "no2": 30 + 10*np.sin(np.arange(len(timestamps))/24)})
    weather = pd.DataFrame({"date": (dates-pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
                            **{v: 5.0 for v in clean_aemet.WEATHER.values()}})
    traffic = pd.DataFrame({"timestamp": timestamps, "sensor_id": 1, "intensity": 100., "occupation": 10.})
    calendar = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "is_holiday": 0, "is_workday": 1})
    return no2, weather, traffic, calendar


def test_grid_gaps_features_and_weather_lag():
    no2, weather, traffic, calendar = source_frames(days=2)
    no2 = no2.drop(index=1)
    frame = join_sources(no2, weather, traffic, calendar, "2023-01-01", "2023-01-02")
    result = add_features(frame)
    assert len(result) == 48
    assert result.weather_date.iloc[0] == "2022-12-25"
    assert pd.isna(result.target_no2.iloc[0])
    assert pd.isna(result.no2_lag_1.iloc[2])
    assert pd.isna(result.target_no2.iloc[-1])
    assert result.no2_lag_24.iloc[24] == result.no2.iloc[0]
    changed = frame.copy()
    changed.loc[30:, "no2"] = 9999
    pd.testing.assert_frame_equal(add_features(changed).iloc[:29], result.iloc[:29])


def test_missing_calendar_rejected():
    no2, weather, traffic, calendar = source_frames(days=2)
    with pytest.raises(ValueError, match="calendario"):
        join_sources(no2, weather, traffic, calendar.iloc[:1], "2023-01-01", "2023-01-02")


def test_training_and_prediction_end_to_end(tmp_path):
    settings = Settings(tmp_path, end="2023-01-14")
    settings.prepare()
    for name, frame in zip(["no2", "aemet", "traffic", "calendar"], source_frames()):
        write_csv(frame, tmp_path / f"data/processed/{name}.csv")
    dataset = build(settings)
    assert len(dataset) == 336
    metrics = train(tmp_path, trees=5)
    assert pd.Timestamp(metrics["train_end"]) + pd.Timedelta(hours=1) < pd.Timestamp(metrics["test_start"])
    assert metrics["baseline_mae"] >= 0
    output = predict(tmp_path)
    assert len(output) == 1
    assert output.predicted_no2.notna().all()
    assert output.timestamp.iloc[0] == dataset.timestamp.iloc[-1]
    with pytest.raises(ValueError, match="zona horaria"):
        predict(tmp_path, "2023-01-01")


def response_mock(body):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [body]
    return response


def test_download_cache_and_versions(tmp_path):
    client = Mock()
    client.get.return_value = response_mock(b"first")
    first = download(client, "https://example.org/data", tmp_path, "resource", ".csv")
    assert download(client, "https://example.org/data", tmp_path, "resource", ".csv") == first
    assert client.get.call_count == 1
    client.get.return_value = response_mock(b"second")
    second = download(client, "https://example.org/data", tmp_path, "resource", ".csv", refresh=True)
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"


def test_incremental_partitions_and_periods(tmp_path, monkeypatch):
    items = [{"id": f"y{year}", "url": f"https://example.org/{year}", "format": "ZIP",
              "hierarchy": [{"hierarchy_name": str(year)}]} for year in [2022, 2023, 2024]]
    monkeypatch.setattr("madrid_air.ingestion.common.resources", lambda *args: items)
    downloader = Mock(return_value=tmp_path / "resource.zip")
    monkeypatch.setattr("madrid_air.ingestion.common.download", downloader)
    list(municipal_files(Mock(), Settings(tmp_path, end="2024-01-10", overlap_days=5), "ds", "no2"))
    assert downloader.call_count == 2
    assert [call.kwargs["refresh"] for call in downloader.call_args_list] == [False, True]
    assert period({"hierarchy": [{"hierarchy_name": "Desde 2025"}]})[1].year == 2262


def test_update_is_idempotent_and_resumable(tmp_path, monkeypatch):
    source = no2_file(tmp_path, [pd.Timestamp("2023-01-01")])
    fetch = Mock(return_value=[source])
    monkeypatch.setattr("madrid_air.ingestion.no2.fetch", fetch)
    settings = Settings(tmp_path, end="2023-01-01")
    update(settings, ["no2"])
    output = tmp_path / "data/processed/no2.csv"
    first = output.read_bytes()
    update(settings, ["no2"])
    assert output.read_bytes() == first
    assert len(pd.read_csv(tmp_path / "data/processed/ingestion_state.csv")) == 1
    # Pérdida del CSV derivado: se reconstruye aunque exista el estado de ingesta.
    output.unlink()
    update(settings, ["no2"])
    assert output.read_bytes() == first


def test_aemet_two_step_api_and_cache(tmp_path, monkeypatch):
    settings = Settings(tmp_path, start="2023-01-15", end="2023-02-28", aemet_key="test-key")
    settings.prepare()
    client = Mock()
    client.get.return_value.json.return_value = {"estado": 200, "datos": "https://example.org/weather"}
    downloader = Mock(return_value=tmp_path / "data.json")
    monkeypatch.setattr("madrid_air.ingestion.aemet.download", downloader)
    list(aemet.fetch(client, settings))
    assert client.get.call_count == 2
    assert "fechaini/2023-01-01T00:00:00UTC" in client.get.call_args_list[0].args[0]
    assert client.get.call_args_list[0].kwargs["headers"] == {"api_key": "test-key"}
    assert "test-key" not in client.get.call_args_list[0].args[0]
    assert downloader.call_count == 2


def test_aemet_errors_and_no_data(tmp_path):
    settings = Settings(tmp_path, start="2023-01-15", end="2023-01-31", aemet_key="test-key")
    client = Mock()
    client.get.return_value.json.return_value = {"estado": 401}
    with pytest.raises(ValueError, match="401"):
        list(aemet.fetch(client, settings))
    client.get.return_value.json.return_value = {"estado": 404}
    assert list(aemet.fetch(client, settings)) == []
    with pytest.raises(ValueError, match="AEMET_API_KEY"):
        list(aemet.fetch(client, Settings(tmp_path)))


def test_failed_download_preserves_cache(tmp_path):
    client = Mock()
    client.get.return_value = response_mock(b"original")
    saved = download(client, "https://example.org/data", tmp_path, "resource", ".csv")
    failed = response_mock(b"")
    failed.iter_content.side_effect = RuntimeError("interrupted")
    client.get.return_value = failed
    with pytest.raises(RuntimeError):
        download(client, "https://example.org/data", tmp_path, "resource", ".csv", refresh=True)
    assert download(client, "https://example.org/data", tmp_path, "resource", ".csv") == saved
    assert saved.read_bytes() == b"original"


def test_complete_job_predicts_locally_and_reuses_model(tmp_path, monkeypatch):
    settings = Settings(tmp_path, end="2023-01-14")
    settings.prepare()

    def fake_update(settings):
        for name, frame in zip(["no2", "aemet", "traffic", "calendar"], source_frames()):
            write_csv(frame, settings.root / f"data/processed/{name}.csv")

    monkeypatch.setattr("madrid_air.pipeline.update", fake_update)
    prediction = run(settings)
    assert prediction.predicted_no2.notna().all()
    assert (tmp_path / "models/random_forest.joblib").exists()
    assert (tmp_path / "data/final/predictions.csv").exists()

    training = Mock(side_effect=AssertionError("No debe reentrenar sin solicitarlo"))
    monkeypatch.setattr("madrid_air.ml.train.train", training)
    run(settings)
    training.assert_not_called()


def test_run_retrain_flag(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    settings.prepare()
    (tmp_path / "models/random_forest.joblib").write_bytes(b"placeholder")
    monkeypatch.setattr("madrid_air.pipeline.update", Mock())
    monkeypatch.setattr("madrid_air.pipeline.build", Mock())
    monkeypatch.setattr("madrid_air.ml.predict.predict", Mock())
    training = Mock()
    monkeypatch.setattr("madrid_air.ml.train.train", training)
    run(settings, retrain=True)
    training.assert_called_once_with(tmp_path)


def test_prediction_explains_missing_prerequisites(tmp_path):
    with pytest.raises(ValueError, match="Falta el dataset"):
        predict(tmp_path)
    write_csv(pd.DataFrame({"timestamp": [], "no2": []}), tmp_path / "data/final/dataset.csv")
    with pytest.raises(ValueError, match="madrid-air train"):
        predict(tmp_path)
