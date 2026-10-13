import pytest

from internet_app.errors import DataLoadError, DataSaveError
from internet_app.loader import load, save


def test_loader_carga_tab_longitud_dataframe(tmp_path, personas_epa):
    archivo = tmp_path / "epa.tab"
    personas_epa.to_csv(archivo, sep="\t", index=False)
    datos = load(archivo)
    assert len(datos) == 5


def test_load_archivo_inexistente(tmp_path):
    with pytest.raises(DataLoadError):
        load(tmp_path / "no_existe.tab")


def test_load_diccionario_invalido_raises_dataloaderror(tmp_path):
    archivo = tmp_path / "diccionario.json"
    archivo.write_text("no es json", encoding="utf-8")
    with pytest.raises(DataLoadError):
        load(archivo)


def test_load_guardado_requiere_carpeta(tmp_path, personas_epa):
    with pytest.raises(DataSaveError):
        save(personas_epa, tmp_path / "no_existe" / "salida.csv")


def test_load_lee_csv_longitud_dataframe(tmp_path, personas_epa):
    archivo = tmp_path / "entrada.csv"
    personas_epa.to_csv(archivo, index=False)
    datos = load(archivo)
    assert len(datos) == 5



def test_load_extension_no_soportada_raises_dataloaderror(tmp_path):
    archivo = tmp_path / "entrada.xlsx"
    archivo.touch()
    with pytest.raises(DataLoadError, match="soportada"):
        load(archivo)



