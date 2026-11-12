import joblib
import numpy as np
import pandas as pd
import pytest

from madrid_air.config import Settings
from madrid_air.ml.daily_forecast import forecast, history_features
from madrid_air.processing.daily import daily_no2
from madrid_air.storage import write_csv


@pytest.mark.parametrize("date,hours", [("2024-03-31", 23), ("2024-10-27", 25)])
def test_daily_coverage_respects_clock_change(date, hours):
    start = pd.Timestamp(date).tz_localize("Europe/Madrid")
    end = (pd.Timestamp(date) + pd.Timedelta(days=1)).tz_localize("Europe/Madrid")
    timestamps = pd.date_range(start, end, freq="h", inclusive="left").tz_convert("UTC")
    hourly = pd.DataFrame({"timestamp": timestamps, "no2": 20.0})
    daily = daily_no2(hourly, date, date)
    assert daily.iloc[0].expected_hours == hours
    assert daily.iloc[0].coverage == 1
    hourly.loc[hourly.index[:8], "no2"] = np.nan
    assert pd.isna(daily_no2(hourly, date, date).iloc[0].no2)


def test_features_cannot_see_future_observations():
    index = pd.date_range("2023-01-01", periods=100)
    daily = pd.DataFrame({"no2": np.arange(100.), "coverage": 1.0}, index=index)
    before = history_features(daily)
    daily.loc[index[50]:, "no2"] = 9999
    pd.testing.assert_frame_equal(before.iloc[:50], history_features(daily).iloc[:50])


def test_forecast_future_dates_backtest_and_final_refit(tmp_path, monkeypatch):
    settings = Settings(tmp_path, end="2024-02-10")
    settings.prepare()
    timestamps = pd.date_range("2023-01-01", "2024-02-09", freq="h", inclusive="left", tz="Europe/Madrid")
    hourly = pd.DataFrame({"timestamp": timestamps.tz_convert("UTC"),
                           "no2": 30 + 10 * np.sin(np.arange(len(timestamps)) / 168)})
    write_csv(hourly, tmp_path / "data/processed/no2.csv")
    dates = pd.date_range("2023-01-01", "2024-03-31")
    calendar = pd.DataFrame({"date": dates, "is_holiday": 0, "is_workday": (dates.dayofweek < 5).astype(int)})
    write_csv(calendar, tmp_path / "data/processed/calendar.csv")
    predictions = forecast(settings, days=30, folds=2, trees=2)
    assert len(predictions) == 30
    assert predictions.date.min() == pd.Timestamp("2024-02-11")
    assert predictions.date.max() == pd.Timestamp("2024-03-11")
    assert predictions.horizon_days.min() == 3  # Último día observado: 8 de febrero.
    backtest = pd.read_csv(tmp_path / "data/final/daily_backtest.csv", parse_dates=["origin_date", "last_training_target"])
    assert len(backtest) == 60
    assert (backtest.last_training_target <= backtest.origin_date).all()
    assert predictions.train_rows.min() > backtest.train_rows.max()
    bundle = joblib.load(tmp_path / "models/daily_random_forests.joblib")
    assert len(bundle["models"]) == 30
    assert (tmp_path / "data/final/forecast.png").stat().st_size > 0
    from madrid_air.ai.client import ResultsClient, AIServiceError
    from madrid_air.ai.daily_report import interpret_forecast
    from madrid_air.ai import google
    import json
    calls = []
    def remote_response(token, model, instructions, facts, **kwargs):
        calls.append(json.loads(facts))
        return json.dumps({"summary": "Resumen simulado.", "rows": [
            {"date": row["date"], "interpretation": "Explicación " + row["date"]}
            for row in reversed(calls[-1]["predictions"])
        ]})
    monkeypatch.setattr(google, "generate_text", remote_response)
    client = ResultsClient(mode="real", token="test", model="test-model", service="google")
    result = interpret_forecast(tmp_path, client)
    assert result.mode == "real"
    assert len(calls) == 1
    assert len(calls[0]["predictions"]) == 30
    assert calls[0]["metadata"]["data_delay_days"] == 2
    first = calls[0]["predictions"][0]
    assert first["difference_previous_day"] is None
    assert first["difference_weekly"] == round(predictions.iloc[0].predicted_no2 - predictions.iloc[0].weekly_baseline, 3)
    assert first["weekday"] == "domingo"
    assert first["is_workday"] == 0
    assert first["evaluated_rows"] == 2
    assert result.text in (tmp_path / "data/final/forecast_report.md").read_text(encoding="utf-8")
    saved = pd.read_csv(tmp_path / "data/final/forecast.csv")
    assert saved.interpretation.tolist() == ["Explicación " + date for date in saved.date]
    np.testing.assert_allclose(saved.predicted_no2, predictions.predicted_no2)
    original_csv = (tmp_path / "data/final/forecast.csv").read_bytes()
    monkeypatch.setattr(google, "generate_text", lambda *args, **kwargs: '{"summary":"Incompleto","rows":[]}')
    with pytest.raises(AIServiceError, match="cada fecha"):
        interpret_forecast(tmp_path, client)
    assert (tmp_path / "data/final/forecast.csv").read_bytes() == original_csv
    def failure(*args, **kwargs):
        raise AIServiceError("API no disponible")
    monkeypatch.setattr(google, "generate_text", failure)
    with pytest.raises(AIServiceError):
        interpret_forecast(tmp_path, client)
    assert interpret_forecast(tmp_path, ResultsClient(mode="mock")).mode == "mock"
    calendar = calendar.iloc[:-60]
    write_csv(calendar, tmp_path / "data/processed/calendar.csv")
    with pytest.raises(ValueError, match="calendario"):
        forecast(settings, days=30, folds=2, trees=2)


@pytest.mark.parametrize("rows", [
    [{"date": "2026-11-13", "interpretation": "A"}] * 2,
    [{"date": "2026-11-13", "interpretation": "A"}, {"date": "2026-11-15", "interpretation": "B"}],
    [{"date": "2026-11-13", "interpretation": "A"}, {"date": "2026-11-14", "interpretation": " "}],
])
def test_daily_response_rejects_wrong_dates_and_empty_text(rows):
    import json
    from madrid_air.ai.client import AIServiceError
    from madrid_air.ai.daily_report import validate_response
    with pytest.raises(AIServiceError):
        validate_response(json.dumps({"summary": "Resumen", "rows": rows}), ["2026-11-13", "2026-11-14"])


def test_cli_ssl_error_explains_recovery(tmp_path, monkeypatch, capsys):
    from madrid_air import cli
    import requests
    def ssl_failure(*args):
        raise requests.exceptions.SSLError("certificate mismatch")
    monkeypatch.setattr(cli, "update", ssl_failure)
    monkeypatch.setattr("sys.argv", ["madrid-air", "forecast", "--root", str(tmp_path), "--ai-mode", "mock"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "forecast --offline" in capsys.readouterr().err
