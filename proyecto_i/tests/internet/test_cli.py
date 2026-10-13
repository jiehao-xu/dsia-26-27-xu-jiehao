import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from internet_app.cli import main, preparar_datos
from internet_app.errors import DataLoadError, ValidationError
from internet_app.validator import EPAValidator


@pytest.mark.parametrize("extension,separador", [(".tab", "\t"), (".csv", ",")])
def test_cli_guarda_metricas_globales(tmp_path, personas_epa, capsys, extension, separador):
    entrada = tmp_path / ("entrada" + extension)
    salida = tmp_path / "resumen.csv"
    personas_epa.to_csv(entrada, sep=separador, index=False)

    main(["--input", str(entrada), "--output", str(salida)])

    resumen = pd.read_csv(salida)
    assert len(resumen) == 1
    fila = resumen.iloc[0]
    assert fila["grupo_edad"] == "20-24"
    assert fila["registros"] == 3
    assert fila["poblacion_estimada"] == 600
    assert fila["poblacion_indicador"] == 100
    assert fila["tasa_indicador_20_24"] == pytest.approx(100 / 6)
    assert fila["tasa_baja_formacion_20_24"] == 50
    assert fila["tasa_formacion_20_24"] == pytest.approx(100 / 3)
    assert "no reproduce" in capsys.readouterr().out


def test_cli_sin_jovenes(tmp_path, personas_epa, capsys):
    entrada = tmp_path / "entrada.tab"
    salida = tmp_path / "resumen.csv"
    datos = personas_epa.loc[personas_epa["EDAD1"] != "20"]
    datos.to_csv(entrada, sep="\t", index=False)
    main(["--input", str(entrada), "--output", str(salida)])
    fila = pd.read_csv(salida).iloc[0]
    assert fila["registros"] == 0
    assert fila["poblacion_estimada"] == 0
    assert pd.isna(fila["tasa_indicador_20_24"])
    assert "sin datos analizables" in capsys.readouterr().out


@pytest.mark.parametrize("factor", [None, "texto", "0", "-1", "inf"])
def test_cli_no_guarda_si_factor_invalido(tmp_path, personas_epa, factor):
    entrada = tmp_path / "entrada.tab"
    salida = tmp_path / "resumen.csv"
    personas_epa.loc[2, "FACTOREL"] = factor
    personas_epa.to_csv(entrada, sep="\t", index=False)
    with pytest.raises(ValidationError, match="FACTOREL"):
        main(["--input", str(entrada), "--output", str(salida)])
    assert not salida.exists()


@pytest.mark.parametrize("columna", ["CCAA", "SEXO1", "EDAD1", "NIVEL", "NFORMA", "CURSR", "CURSNR"])
def test_preparacion_rechaza_codigos_invalidos(personas_epa, diccionario_epa, columna):
    personas_epa.loc[2, columna] = "desconocido"
    with pytest.raises(ValidationError, match=columna):
        preparar_datos(personas_epa, EPAValidator(diccionario_epa))


def test_preparacion_no_modifica_original(personas_epa, diccionario_epa):
    original = personas_epa.copy(deep=True)
    datos = preparar_datos(personas_epa, EPAValidator(diccionario_epa))
    assert datos["FACTOREL"].tolist() == [100, 300, 200, 50, 25]
    assert_frame_equal(personas_epa, original)


def test_preparacion_rechaza_edad_incoherente(personas_epa, diccionario_epa):
    personas_epa.loc[2, "NIVEL"] = "2"
    with pytest.raises(ValidationError, match="no corresponden"):
        preparar_datos(personas_epa, EPAValidator(diccionario_epa))


def test_cli_exige_argumentos():
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_cli_rechaza_json_como_datos(tmp_path):
    entrada = tmp_path / "entrada.json"
    entrada.write_text("{}", encoding="utf-8")
    with pytest.raises(DataLoadError, match="CSV o TAB"):
        main(["--input", str(entrada), "--output", str(tmp_path / "salida.csv")])


def test_cli_rechaza_csv_como_diccionario(tmp_path, personas_epa):
    entrada = tmp_path / "entrada.csv"
    personas_epa.to_csv(entrada, index=False)
    with pytest.raises(DataLoadError, match="objeto JSON"):
        main(["--input", str(entrada), "--output", str(tmp_path / "salida.csv"),
              "--dictionary", str(entrada)])


@pytest.mark.integration
def test_cli_desde_terminal(tmp_path, personas_epa):
    entrada = tmp_path / "entrada.tab"
    salida = tmp_path / "resumen.csv"
    personas_epa.to_csv(entrada, sep="\t", index=False)
    proyecto = Path(__file__).resolve().parents[2]
    resultado = subprocess.run(
        [sys.executable, "-B", "-m", "internet_app.cli",
         "--input", str(entrada), "--output", str(salida)],
        cwd=proyecto, capture_output=True, text=True, timeout=30,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert pd.read_csv(salida).loc[0, "poblacion_estimada"] == 600
