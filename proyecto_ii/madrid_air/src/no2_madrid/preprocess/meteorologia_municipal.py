"""Limpia los datos horarios conservando estaciones y magnitudes."""

import pandas as pd

from no2_madrid.preprocess.common import (
    RAW_DIR, PROCESS_DIR, comprobar_claves, fechas, guardar_csv, guardar_informe,
)

PARAMETROS = {
    81: "velocidad_viento", 82: "direccion_viento", 83: "temperatura",
    86: "humedad_relativa", 87: "presion", 88: "radiacion_solar", 89: "precipitacion",
}


def limpiar(datos):
    datos = datos.loc[(datos["PROVINCIA"] == 28) & (datos["MUNICIPIO"] == 79)].drop_duplicates().copy()
    datos["FECHA"] = fechas(datos)
    datos = datos.loc[datos["FECHA"].notna()].copy()
    horas = [f"H{hora:02d}" for hora in range(1, 25)]
    for hora in range(1, 25):
        valor = pd.to_numeric(datos[f"H{hora:02d}"], errors="coerce")
        valido = datos[f"V{hora:02d}"].astype(str).str.strip().eq("V")
        datos[f"H{hora:02d}"] = valor.where(valido).replace([float("inf"), -float("inf")], float("nan"))
    datos["N_HORAS_VALIDAS"] = datos[horas].notna().sum(axis=1)
    datos["PARAMETRO"] = datos["MAGNITUD"].map(PARAMETROS)
    if datos["PARAMETRO"].isna().any():
        raise ValueError("Hay una magnitud meteorológica desconocida; revisa PARAMETROS.")
    comprobar_claves(datos, ["FECHA", "ESTACION", "MAGNITUD"])
    columnas = ["FECHA", "ANO", "MES", "DIA", "ESTACION", "MAGNITUD", "PARAMETRO"]
    return datos[columnas + horas + ["N_HORAS_VALIDAS"]].sort_values(
        ["FECHA", "ESTACION", "MAGNITUD"], ignore_index=True,
    )


def main():
    archivos = sorted((RAW_DIR / "meteorologia_municipal").glob("meteorologicos_horarios_*.csv"))
    if not archivos:
        raise FileNotFoundError("No se encontraron los CSV meteorológicos anuales.")
    for origen in archivos:
        resultado = limpiar(pd.read_csv(origen, sep=";", encoding="utf-8-sig"))
        destino = PROCESS_DIR / "meteorologia_municipal" / origen.name
        guardar_csv(resultado, destino)
        guardar_informe(origen, destino, filas=len(resultado),
                        horas_validas=int(resultado["N_HORAS_VALIDAS"].sum()))
        print(f"Meteorología: {destino.name}, {len(resultado)} filas", flush=True)


if __name__ == "__main__":
    main()
