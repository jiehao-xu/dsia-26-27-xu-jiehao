"""Descarga reproducible del calendario municipal."""
from pathlib import Path
from no2_madrid.ingestion.portal import latest_csv
from no2_madrid.io import write_json
from no2_madrid.preprocess.common import guardar_csv

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "calendar"


def main():
    frame, source = latest_csv("300082-0-calendario_laboral", resource="300082-1-calendario_laboral-csv")
    required = {"Dia", "laborable / festivo / domingo festivo"}
    if not required <= set(frame):
        raise ValueError("El formato del calendario municipal ha cambiado.")
    destination = OUTPUT_DIR / "300082-1-calendario_laboral-csv.csv"
    guardar_csv(frame, destination)
    write_json(destination.with_suffix(".source.json"), {"source": source})


if __name__ == "__main__":
    main()
