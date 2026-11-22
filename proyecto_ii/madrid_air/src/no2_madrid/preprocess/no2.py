"""Limpia NO2 por estación y día, sin calcular medias de Madrid."""

import pandas as pd

from no2_madrid.preprocess.common import (
    RAW_DIR, PROCESS_DIR, comprobar_claves, fechas, guardar_csv, guardar_informe,
)


def limpiar(datos):
    datos = datos.loc[
        (datos["MAGNITUD"] == 8) & (datos["PROVINCIA"] == 28)
        & (datos["MUNICIPIO"] == 79)
    ].drop_duplicates().copy()
    partes = []
    for dia in range(1, 32):
        parte = datos[["ANO", "MES", "ESTACION"]].copy()
        parte["DIA"] = dia
        parte["FECHA"] = fechas(parte)
        valor = pd.to_numeric(datos[f"D{dia:02d}"], errors="coerce").replace(
            [float("inf"), -float("inf")], float("nan"),
        )
        valido = datos[f"V{dia:02d}"].astype(str).str.strip().eq("V") & valor.ge(0)
        parte["NO2"] = valor.where(valido)
        parte["VALIDO"] = valido.astype(int)
        partes.append(parte.loc[parte["FECHA"].notna()])
    resultado = pd.concat(partes, ignore_index=True)
    comprobar_claves(resultado, ["FECHA", "ESTACION"])
    return resultado[["FECHA", "ANO", "MES", "DIA", "ESTACION", "NO2", "VALIDO"]].sort_values(
        ["FECHA", "ESTACION"], ignore_index=True,
    )


def main():
    archivos = sorted((RAW_DIR / "no2").glob("calidad_aire_diario_*.csv"))
    if not archivos:
        raise FileNotFoundError("No se encontraron los CSV anuales de NO2.")
    for origen in archivos:
        resultado = limpiar(pd.read_csv(origen, sep=";", encoding="utf-8-sig"))
        destino = PROCESS_DIR / "no2" / origen.name
        guardar_csv(resultado, destino)
        guardar_informe(origen, destino, filas=len(resultado),
                        mediciones_validas=int(resultado["VALIDO"].sum()),
                        estaciones=int(resultado["ESTACION"].nunique()))
        print(f"NO2: {destino.name}, {len(resultado)} filas", flush=True)


if __name__ == "__main__":
    main()
