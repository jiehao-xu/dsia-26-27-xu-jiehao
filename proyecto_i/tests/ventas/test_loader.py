import pytest
from pandas.testing import assert_frame_equal

from ventas_app.errors import DataLoadError, DataSaveError
from ventas_app.loader import CsvSalesRepository


def test_load_csv(tmp_path, ventas):
    archivo = tmp_path / "entrada.csv"
    ventas.to_csv(archivo, index=False)
    repositorio = CsvSalesRepository()

    resultado = repositorio.load(archivo)

    assert_frame_equal(resultado, ventas.reset_index(drop=True))


def test_load_archivo_inexistente(tmp_path):
    archivo = tmp_path / "inexistente.csv"
    repositorio = CsvSalesRepository()

    with pytest.raises(DataLoadError, match="inexistente.csv"):
        repositorio.load(archivo)


def test_save_crea_archivo_sin_guardar_indice(tmp_path, ventas):
    archivo = tmp_path / "salida.csv"
    repositorio = CsvSalesRepository()

    repositorio.save(ventas, archivo)

    assert archivo.is_file()
    ventas_guardadas = repositorio.load(archivo)
    assert_frame_equal(ventas_guardadas, ventas.reset_index(drop=True))


def test_save_sobrescribe_archivo_existente(tmp_path, ventas):
    archivo = tmp_path / "salida.csv"
    repositorio = CsvSalesRepository()
    repositorio.save(ventas, archivo)
    nuevas_ventas = ventas.iloc[:1]

    repositorio.save(nuevas_ventas, archivo)

    ventas_guardadas = repositorio.load(archivo)
    assert_frame_equal(ventas_guardadas, nuevas_ventas.reset_index(drop=True))


def test_save_rechaza_carpeta_inexistente(tmp_path, ventas):
    archivo = tmp_path / "no_existe" / "salida.csv"
    repositorio = CsvSalesRepository()

    with pytest.raises(DataSaveError, match="no_existe"):
        repositorio.save(ventas, archivo)

    assert not archivo.exists()
