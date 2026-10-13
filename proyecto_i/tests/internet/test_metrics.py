import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from internet_app.metrics import (
    poblacion_estimada,
    poblacion_indicador,
    preparar_indicador,
    tasa_baja_formacion,
    tasa_participacion_formacion,
    tasa_ponderada,
)


@pytest.fixture
def datos_metricas(personas_epa):
    datos = personas_epa.copy()
    datos["FACTOREL"] = pd.to_numeric(datos["FACTOREL"])
    return datos


def test_indicador_solo_para_20_24(datos_metricas):
    validos = datos_metricas.copy()
    original = validos.copy(deep=True)
    jovenes = preparar_indicador(validos)
    assert jovenes.index.tolist() == [2, 5, 9]
    # La segunda persona tiene estudios superiores; la tercera está de vacaciones.
    assert jovenes["baja_formacion_sin_estudios"].tolist() == [True, False, False]
    assert_frame_equal(validos, original)


@pytest.mark.parametrize("columna,codigo", [("CURSR", "1"), ("CURSR", "2"), ("CURSNR", "1"), ("CURSNR", "2")])
def test_formacion_o_vacaciones_no_cumplen_indicador(datos_metricas, columna, codigo):
    datos_metricas.loc[2, columna] = codigo
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    assert not jovenes.loc[2, "baja_formacion_sin_estudios"]


def test_tasa_usa_factores_y_no_recuento(datos_metricas):
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    # Una de tres personas cumple, pero pesa 100 de un total de 600.
    assert tasa_ponderada(jovenes) == pytest.approx(100 * 100 / 600)


def test_sin_personas_en_grupo(datos_metricas):
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos.loc[validos["EDAD1"] != "20"])
    assert tasa_ponderada(jovenes) is None


def test_poblacion_estimada_suma_factores(datos_metricas):
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    assert poblacion_estimada(jovenes) == 600
    assert poblacion_indicador(jovenes) == 100


def test_baja_formacion_incluye_quienes_estudian(datos_metricas):
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    # Pesa 100 quien no estudia y 200 quien está de vacaciones.
    assert tasa_baja_formacion(jovenes) == pytest.approx(50)
    assert tasa_participacion_formacion(jovenes) == pytest.approx(100 / 3)


def test_nuevas_metricas_sin_personas(datos_metricas):
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos.iloc[:0])
    assert poblacion_estimada(jovenes) == 0
    assert poblacion_indicador(jovenes) == 0
    assert tasa_baja_formacion(jovenes) is None
    assert tasa_participacion_formacion(jovenes) is None


@pytest.mark.parametrize("nivel", ["AN", "P1", "P2", "S1", "SG", "SP", "SU"])
def test_indicador_segun_nivel_educativo(datos_metricas, nivel):
    datos_metricas.loc[2, "NFORMA"] = nivel
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    esperado = nivel in {"AN", "P1", "P2", "S1"}
    assert jovenes.loc[2, "baja_formacion_sin_estudios"] == esperado


def test_tasa_cero_si_nadie_cumple(datos_metricas):
    datos_metricas["NFORMA"] = "SU"
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    assert tasa_ponderada(jovenes) == 0


def test_tasa_cien_si_todos_cumplen(datos_metricas):
    datos_metricas["NFORMA"] = "S1"
    datos_metricas["CURSR"] = "3"
    datos_metricas["CURSNR"] = "3"
    validos = datos_metricas.copy()
    jovenes = preparar_indicador(validos)
    assert tasa_ponderada(jovenes) == 100
