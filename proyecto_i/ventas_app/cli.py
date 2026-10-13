import argparse
from pathlib import Path
from ventas_app.validator import SalesValidator
from ventas_app.loader import CsvSalesRepository
from ventas_app.metrics import *
import logging

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()

    # Obtenemos los parametros de entrada
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # Ruta del fichero de entrada
    data_path = Path(__file__).resolve().parent.parent / args.input

    # Ruta del fichero de salida
    save_path = Path(__file__).resolve().parent.parent / args.output

    # Instanciación de clases
    repo = CsvSalesRepository()
    validator = SalesValidator()
    
    # Carga del csv
    frame = repo.load(data_path)
    logging.info("csv cargado")

    # Validacion del dataframe
    validator.validar_columnas(frame)
    validator.validar_fechas(frame)
    records, errors = validator.validar_ventas(frame)
    logging.info("data frame validado")

    # Calculo de metricas
    records = drop_id(records)
    records["total_by_region"] = total_by_region(records)
    records["total_by_month"] = total_by_month(records)
    records["total_by_product"] = total_by_product(records)
    
    # Guardado del csv
    repo.save(records, save_path)
    logging.info("data frame guardado")

if __name__ == "__main__":
    main()