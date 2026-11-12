import argparse
import json
import logging
from pathlib import Path

import requests

from madrid_air.config import Settings
from madrid_air.ai.client import AIServiceError, ResultsClient
from madrid_air.pipeline import SOURCES, analyze, build, run, update


def main():
    parser = argparse.ArgumentParser(description="Madrid Air: pronóstico diario de NO2 con CSV + Pandas.")
    parser.add_argument("command", choices=["forecast", "forecast-analyze", "update", "build", "run", "train", "predict", "analyze"])
    parser.add_argument("--days", type=int, default=30, help="Fechas futuras para forecast (1–90)")
    parser.add_argument("--folds", type=int, default=3, help="Cortes históricos para evaluar forecast (mínimo 2)")
    parser.add_argument("--offline", action="store_true", help="forecast: utilizar los CSV existentes sin descargar")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--start", default="2023-01-01", help="Primer día local, incluido")
    parser.add_argument("--end", help="Último día local, incluido; por defecto hoy")
    parser.add_argument("--overlap-days", type=int, default=14)
    parser.add_argument("--sources", nargs="+", choices=list(SOURCES), help="Solo para update")
    parser.add_argument("--timestamp", help="Instante con zona horaria para predict/analyze")
    parser.add_argument("--ai-mode", choices=["mock", "real"], help="forecast/forecast-analyze: real por defecto; run/analyze: AI_MODE o mock")
    parser.add_argument("--retrain", action="store_true", help="Reentrenar el modelo durante run")
    args = parser.parse_args()
    if args.offline and args.command != "forecast":
        parser.error("--offline solo se admite con forecast")
    if args.sources and args.command != "update":
        parser.error("--sources solo se admite con update")
    if args.retrain and args.command != "run":
        parser.error("--retrain solo se admite con run")
    if args.timestamp and args.command not in {"predict", "analyze"}:
        parser.error("--timestamp solo se admite con predict o analyze")
    if args.ai_mode and args.command not in {"run", "analyze", "forecast", "forecast-analyze"}:
        parser.error("--ai-mode requiere run, analyze, forecast o forecast-analyze")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        settings = Settings.from_env(args.root, start=args.start, end=args.end, overlap_days=args.overlap_days)
        if args.command in {"forecast", "forecast-analyze"}:
            from madrid_air.ai.daily_report import interpret_forecast
            ai_client = ResultsClient.from_env(args.ai_mode or "real")
        if args.command == "forecast-analyze":
            print(interpret_forecast(settings.root, ai_client).text)
        if args.command == "forecast":
            from madrid_air.ml.daily_forecast import forecast
            if not args.offline:
                update(settings, ["no2", "calendar"])
            print(forecast(settings, days=args.days, folds=args.folds).to_string(index=False))
            print(interpret_forecast(settings.root, ai_client).text)
            print(f"Resultados, gráfico y evaluación: {settings.root / 'data/final'}")
        if args.command == "run":
            ai_client = ResultsClient.from_env(args.ai_mode)
            print(run(settings, retrain=args.retrain, ai_client=ai_client).to_string(index=False))
        if args.command == "analyze":
            ai_client = ResultsClient.from_env(args.ai_mode)
            print(analyze(settings, ai_client, args.timestamp).to_string(index=False))
        if args.command == "update":
            update(settings, args.sources)
        if args.command == "build":
            build(settings)
        if args.command == "train":
            from madrid_air.ml.train import train
            print(json.dumps(train(settings.root), indent=2))
        if args.command == "predict":
            from madrid_air.ml.predict import predict
            print(predict(settings.root, args.timestamp).to_string(index=False))
    except (ValueError, FileNotFoundError, AIServiceError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    except requests.exceptions.SSLError:
        parser.exit(1, "Error SSL: no se pudo verificar el certificado del servidor. "
                    "Revisa la red, VPN o certificado del proveedor. No desactives la verificación TLS. "
                    "Si ya tienes los CSV, usa forecast --offline; para interpretar resultados "
                    "existentes, usa forecast-analyze.\n")
    except requests.RequestException as exc:
        parser.exit(1, f"Error HTTP ({type(exc).__name__}). Los archivos completados se conservan; vuelve a ejecutar el comando.\n")


if __name__ == "__main__":
    main()
