"""Separa la fecha del calendario y conserva el tipo de día."""

import pandas as pd

from no2_madrid.preprocess.common import (
    RAW_DIR, PROCESS_DIR, comprobar_claves, guardar_csv, guardar_informe,
)


def limpiar(datos):
    resultado = pd.DataFrame()
    resultado["FECHA"] = pd.to_datetime(datos["Dia"], format="%d/%m/%Y", errors="raise")
    resultado["ANO"] = resultado["FECHA"].dt.year
    resultado["MES"] = resultado["FECHA"].dt.month
    resultado["DIA"] = resultado["FECHA"].dt.day
    resultado["TIPO_DIA"] = datos["laborable / festivo / domingo festivo"].str.strip().str.lower()
    if not resultado["TIPO_DIA"].isin(["laborable", "sabado", "domingo", "festivo"]).all():
        raise ValueError("Hay tipos de día desconocidos en el calendario.")
    resultado = resultado.drop_duplicates()
    comprobar_claves(resultado, ["FECHA"])
    return resultado.sort_values("FECHA", ignore_index=True)


def main():
    origen = RAW_DIR / "calendar" / "300082-1-calendario_laboral-csv.csv"
    resultado = limpiar(pd.read_csv(origen, sep=";", encoding="utf-8-sig"))
    destino = PROCESS_DIR / "calendar" / "calendario_laboral.csv"
    guardar_csv(resultado, destino)
    guardar_informe(origen, destino, filas=len(resultado))
    print(f"Calendario: {len(resultado)} fechas, {destino}", flush=True)


if __name__ == "__main__":
    main()
