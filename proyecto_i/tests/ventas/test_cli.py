import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ventas_app import cli
from ventas_app.errors import ValidationError


PROYECTO = Path(__file__).resolve().parents[2]


def test_cli_modulo_genera_csv_correcto(tmp_path, ventas):
    entrada = tmp_path / "entrada.csv"
    salida = tmp_path / "salida.csv"
    frame = ventas.copy()
    frame.loc[5, "unidades"] = 0
    frame.to_csv(entrada, index=False)

    # Ejecutamos el mismo módulo que se utiliza desde la terminal.
    comando = [
        sys.executable, "-B", "-m", "ventas_app.cli",
        "--input", str(entrada),
        "--output", str(salida),
    ]
    proceso = subprocess.run(
        comando,
        cwd=PROYECTO,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proceso.returncode == 0, proceso.stderr
    resultado = pd.read_csv(salida)
    esperado = pd.DataFrame({
        "fecha": ["2026-01-09", "2026-02-05", "2027-01-09"],
        "region": ["Norte", "Norte", "Sur"],
        "producto": ["Sensor", "Cable", "Cable"],
        "unidades": [2, 4, 1],
        "precio_unitario": [10.0, 5.0, 5.0],
        "importe": [20.0, 20.0, 5.0],
        "total_by_region": [40.0, 40.0, 5.0],
        "total_by_month": [20.0, 20.0, 5.0],
        "total_by_product": [20.0, 25.0, 25.0],
    })
    assert_frame_equal(resultado, esperado, check_dtype=False)
    assert_frame_equal(pd.read_csv(entrada), frame.reset_index(drop=True))


@pytest.mark.parametrize("argumentos", [[], ["--input", "entrada.csv"], ["--output", "salida.csv"]])
def test_cli_exige_input_y_output(monkeypatch, capsys, argumentos):
    monkeypatch.setattr(sys, "argv", ["ventas_app.cli", *argumentos])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "required" in capsys.readouterr().err


def test_cli_no_guarda_si_falta_una_columna(tmp_path, ventas, monkeypatch):
    entrada = tmp_path / "entrada.csv"
    salida = tmp_path / "salida.csv"
    ventas = ventas.drop(columns="fecha")
    ventas.to_csv(entrada, index=False)
    argumentos = ["ventas_app.cli", "--input", str(entrada), "--output", str(salida)]
    monkeypatch.setattr(sys, "argv", argumentos)

    with pytest.raises(ValidationError):
        cli.main()

    assert not salida.exists()


def test_cli_no_guarda_si_hay_una_fecha_invalida(tmp_path, ventas, monkeypatch):
    entrada = tmp_path / "entrada.csv"
    salida = tmp_path / "salida.csv"
    ventas.loc[2, "fecha"] = "2026-02-30"
    ventas.to_csv(entrada, index=False)
    argumentos = ["ventas_app.cli", "--input", str(entrada), "--output", str(salida)]
    monkeypatch.setattr(sys, "argv", argumentos)

    with pytest.raises(ValidationError):
        cli.main()

    assert not salida.exists()
