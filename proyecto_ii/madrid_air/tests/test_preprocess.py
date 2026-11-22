import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from no2_madrid.preprocess import meteorologia_municipal, no2, traffic, work_calendar
from no2_madrid.preprocess.common import esta_actualizado, informe_path


class LimpiezaTests(unittest.TestCase):
    def test_no2_fecha_real_calidad_y_otros_contaminantes(self):
        fila = {"ANO": 2024, "MES": 2, "ESTACION": 4, "MAGNITUD": 8,
                "PROVINCIA": 28, "MUNICIPIO": 79}
        for dia in range(1, 32):
            fila[f"D{dia:02d}"] = 20
            fila[f"V{dia:02d}"] = "V"
        fila.update(D01=0, D02=999, V02="N", D03=-1, D04=float("inf"))
        otra = {**fila, "MAGNITUD": 7}
        resultado = no2.limpiar(pd.DataFrame([fila, fila, otra]))
        self.assertEqual(len(resultado), 29)
        self.assertEqual(resultado.loc[0, "NO2"], 0)
        self.assertTrue(resultado.loc[1:3, "NO2"].isna().all())
        self.assertEqual(resultado["VALIDO"].sum(), 26)
        self.assertEqual(resultado["FECHA"].max(), pd.Timestamp("2024-02-29"))

    def test_meteo_conserva_temperatura_negativa_y_anula_hora_invalida(self):
        fila = {"ANO": 2024, "MES": 2, "DIA": 29, "ESTACION": 4,
                "MAGNITUD": 83, "PROVINCIA": 28, "MUNICIPIO": 79}
        for hora in range(1, 25):
            fila[f"H{hora:02d}"] = -3
            fila[f"V{hora:02d}"] = "V"
        fila.update(H02=999, V02="N")
        resultado = meteorologia_municipal.limpiar(pd.DataFrame([fila, fila]))
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.loc[0, "H01"], -3)
        self.assertTrue(pd.isna(resultado.loc[0, "H02"]))
        self.assertEqual(resultado.loc[0, "N_HORAS_VALIDAS"], 23)

    def test_calendario_separa_fecha_y_elimina_descripciones(self):
        datos = pd.DataFrame({"Dia": ["29/02/2024"], "Dia_semana": ["jueves"],
                              "laborable / festivo / domingo festivo": [" laborable "],
                              "Tipo de Festivo": [""], "Festividad": [""]})
        resultado = work_calendar.limpiar(datos)
        self.assertEqual(resultado.loc[0, ["ANO", "MES", "DIA"]].tolist(), [2024, 2, 29])
        self.assertEqual(resultado.columns.tolist(), ["FECHA", "ANO", "MES", "DIA", "TIPO_DIA"])

    def test_trafico_filtros_y_resultado_independiente_de_bloques(self):
        base = {"id": 1, "fecha": "2023-01-01 00:15:00", "tipo_elem": "URB",
                "intensidad": 0, "ocupacion": 2, "carga": 3, "vmed": 0,
                "error": "N", "periodo_integracion": 15}
        filas = [base, {**base, "id": 2, "tipo_elem": "C30", "vmed": 50},
                 {**base, "error": "E"}, {**base, "periodo_integracion": 0},
                 {**base, "tipo_elem": "other"}, {**base, "fecha": "mal"},
                 {**base, "id": 3, "intensidad": -1, "ocupacion": 101}]
        datos = pd.DataFrame(filas)
        limpio = traffic.limpiar(datos).reset_index(drop=True)
        self.assertEqual(len(limpio), 3)
        self.assertTrue(pd.isna(limpio.loc[0, "VELOCIDAD_MEDIA"]))
        self.assertEqual(limpio.loc[0, "INTENSIDAD"], 0)
        self.assertEqual(limpio.loc[1, "VELOCIDAD_MEDIA"], 50)
        self.assertTrue(pd.isna(limpio.loc[2, "INTENSIDAD"]))
        self.assertTrue(pd.isna(limpio.loc[2, "OCUPACION"]))
        with TemporaryDirectory() as carpeta:
            origen = Path(carpeta) / "origen.csv"
            datos.to_csv(origen, sep=";", index=False)
            resultados = []
            for tamano in [1, 4, 100]:
                destino = Path(carpeta) / f"limpio_{tamano}.csv.gz"
                traffic.procesar_archivo(origen, destino, chunksize=tamano)
                resultados.append(pd.read_csv(destino, sep=";"))
                with gzip.open(destino, "rt") as archivo:
                    self.assertEqual(archivo.read().count("FECHA_HORA"), 1)
                informe = json.loads(informe_path(destino).read_text(encoding="utf-8"))
                self.assertEqual(informe["filas_descartadas"], 4)
                self.assertTrue(esta_actualizado(origen, destino))
            pd.testing.assert_frame_equal(resultados[0], resultados[1])
            pd.testing.assert_frame_equal(resultados[0], resultados[2])
            origen.write_text("modificado", encoding="utf-8")
            self.assertFalse(esta_actualizado(origen, destino))


if __name__ == "__main__":
    unittest.main()
