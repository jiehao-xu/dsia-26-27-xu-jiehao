from dataclasses import replace
from unittest.mock import Mock

import pandas as pd
import pytest

from madrid_air.ai.client import AIServiceError, ResultsClient, ResultsContext
from madrid_air.config import Settings
from madrid_air.pipeline import analyze, run
from madrid_air.storage import write_csv
from test_pipeline import source_frames


def results():
    return ResultsContext(
        timestamp="2023-02-01T10:00:00Z", target_timestamp="2023-02-01T11:00:00Z",
        predicted_no2=32.5, mae=4.0, rmse=6.0, baseline_mae=5.0, baseline_rmse=7.0,
        test_start="2023-01-25T00:00:00Z", test_end="2023-01-31T23:00:00Z", test_rows=168,
    )


@pytest.mark.parametrize("mae,baseline,comparison", [(4, 5, "mejora"), (6, 5, "empeora"), (0, 0, "iguala")])
def test_mock_explains_comparison_without_network(monkeypatch, mae, baseline, comparison):
    constructor = Mock(side_effect=AssertionError("El mock no debe construir el SDK"))
    monkeypatch.setattr("madrid_air.ai.google.generate_text", constructor)
    context = replace(results(), mae=mae, baseline_mae=baseline)
    client = ResultsClient()
    answer = client.interpret(context)
    assert answer == client.interpret(context)
    assert answer.mode == "mock"
    assert comparison in answer.text
    assert "32.50" in answer.text
    assert context.test_start in answer.text
    assert context.target_timestamp in answer.text
    assert "no un intervalo de confianza" in answer.text
    constructor.assert_not_called()



@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_invalid_metrics_rejected(value):
    with pytest.raises(ValueError, match="finitos"):
        replace(results(), mae=value)


def test_cli_real_without_token_fails_before_job(tmp_path, monkeypatch, capsys):
    from madrid_air.cli import main

    monkeypatch.setattr("sys.argv", ["madrid-air", "run", "--root", str(tmp_path), "--ai-mode", "real"])
    job = Mock(side_effect=AssertionError("No debe empezar"))
    monkeypatch.setattr("madrid_air.cli.run", job)
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "GOOGLE_API_KEY" in capsys.readouterr().err
    job.assert_not_called()


def test_job_and_standalone_analysis_keep_numeric_results(tmp_path, monkeypatch):
    settings = Settings(tmp_path, end="2023-01-14")
    settings.prepare()

    def fake_update(settings):
        for name, frame in zip(["no2", "aemet", "traffic", "calendar"], source_frames()):
            write_csv(frame, settings.root / f"data/processed/{name}.csv")

    monkeypatch.setattr("madrid_air.pipeline.update", fake_update)
    report = run(settings, ai_client=ResultsClient())
    numeric = pd.read_csv(tmp_path / "data/final/predictions.csv")
    assert report.predicted_no2.iloc[0] == pytest.approx(numeric.predicted_no2.iloc[0])
    assert report.ai_mode.tolist() == ["mock"]
    assert "baseline_mae" in report
    assert (tmp_path / "data/final/analysis.csv").exists()

    # El informe toma las métricas del modelo, no de un JSON que podría desincronizarse.
    (tmp_path / "models/metrics.json").unlink()
    again = analyze(settings, ResultsClient())
    assert again.mae.iloc[0] == report.mae.iloc[0]
    assert again.interpretation.iloc[0] == report.interpretation.iloc[0]

    # Un fallo remoto no elimina la predicción ni sobrescribe un informe completo.
    saved = (tmp_path / "data/final/analysis.csv").read_bytes()
    failing_client = Mock()
    failing_client.interpret.side_effect = AIServiceError("No disponible")
    with pytest.raises(AIServiceError):
        analyze(settings, failing_client)
    assert (tmp_path / "data/final/predictions.csv").exists()
    assert (tmp_path / "data/final/analysis.csv").read_bytes() == saved
