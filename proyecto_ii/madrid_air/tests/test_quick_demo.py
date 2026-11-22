"""Prueba del paquete real distribuido sin datos locales, red ni entrenamiento."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from no2_madrid import quick_demo as module


def test_quick_demo_works_without_local_data_credentials_or_training(tmp_path, monkeypatch):
    import dotenv
    import requests
    from no2_madrid import train
    def forbidden(*args, **kwargs):
        raise AssertionError("La prueba rápida no debe descargar, entrenar ni leer .env.")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_MODE", "real")
    monkeypatch.setattr(dotenv, "load_dotenv", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(train, "train", forbidden)
    result = module.quick_demo(tmp_path / "output")
    assert result["scope"] == "Madrid"
    assert result["network_station_count"] == 24
    assert result["model"] == "ridge_no_traffic"
    assert result["no2"] == pytest.approx(28.75443833095471)
    assert result["ai_status"] == "mock"
    assert result["quick_demo"]["reference_prediction_matches"] is True
    assert result["quick_demo"]["training_performed"] is False
    assert not (tmp_path / "data").exists()
    assert (tmp_path / "output/reports/runs/prediction_2026-11-01.json").exists()


def test_quick_demo_checks_integrity_before_loading_model(tmp_path, monkeypatch):
    import joblib
    sample = tmp_path / "sample"
    shutil.copytree(Path(module.__file__).parent / "sample", sample)
    with (sample / "daily.csv").open("a", encoding="utf-8") as stream:
        stream.write("modified")
    def forbidden(*args, **kwargs):
        raise AssertionError("No se debe cargar un modelo con una muestra modificada.")
    monkeypatch.setattr(joblib, "load", forbidden)
    with pytest.raises(ValueError, match="modificado: daily.csv"):
        module.quick_demo(tmp_path / "output", sample_dir=sample)


def test_quick_demo_cli_from_an_empty_directory(tmp_path):
    result = subprocess.run([sys.executable, "-m", "no2_madrid", "quick-demo", "--dir", str(tmp_path / "output")],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["scope"] == "Madrid"
    assert value["quick_demo"]["real_data"] is True
    assert value["quick_demo"]["downloads_performed"] is False
