import argparse
from pathlib import Path
from validator import SalesValidator
from loader import CsvSalesRepository
from metrics import SalesMetrics
import logging

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()

    # Obtenemos los valores de entrada

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    data_path = Path(__file__).resolve().parent.parent / args.input
    save_path = Path(__file__).resolve().parent.parent / args.output
    repo = CsvSalesRepository()
    validator = SalesValidator()
    metrics = SalesMetrics()

    frame = repo.load(data_path)

    logging.info("csv cargado")

    records, errors = validator.validar_ventas(frame)

    logging.info("data frame validado")

    print(f"Registros válidos: {len(records)} | inválidos: {len(errors)}")
    print("Importe por región:")

    for region, total in metrics.total_by_region(records).items():
        print(f" {region}: {total:.2f}")

    repo.save(records, save_path)
    
    logging.info("data frame guardado")

if __name__ == "__main__":
    main()