"""Interfaz del Proyecto II. No realiza llamadas reales de IA salvo AI_MODE=real."""
import argparse
from dataclasses import replace
import json
import logging
from pathlib import Path
import sys

from no2_madrid.config import Settings


def parser():
    p = argparse.ArgumentParser(description="NO₂ Madrid: pipeline del Proyecto II")
    p.add_argument("--data-dir", type=Path)
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--without-traffic", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Descargar fuentes; tráfico puede ocupar muchos GB")
    ingest.add_argument("--source", choices=["no2", "municipal", "calendar", "traffic", "metadata", "all"], default="all")
    ingest.add_argument("--start", default="2023-01-01")
    ingest.add_argument("--end", default="2026-10-31")
    ingest.add_argument("--refresh", action="store_true")
    pre = sub.add_parser("preprocess", help="Limpiar originales")
    pre.add_argument("--workers", type=int, default=1)
    sub.add_parser("build-dataset", help="Integrar las fuentes y generar informe de calidad")
    training = sub.add_parser("train", help="Entrenar, seleccionar y evaluar")
    training.add_argument("--train-end", default="2024-12-31")
    training.add_argument("--validation-end", default="2025-12-31")
    for name in ("predict", "run"):
        command = sub.add_parser(name)
        command.add_argument("--date")
        command.add_argument("--ai-mode", choices=["mock", "real"])
        if name == "run":
            command.add_argument("--prepare", action="store_true", help="Ejecutar también limpieza; no descarga ni reentrena")
            command.add_argument("--workers", type=int, default=1)
    demonstration = sub.add_parser("demo", help="Flujo sintético independiente, sin red ni credenciales")
    demonstration.add_argument("--dir", type=Path, default=Path("artifacts/demo"))
    quick = sub.add_parser("quick-demo", help="Predicción real con modelo y muestra incluidos; sin descargar ni entrenar")
    quick.add_argument("--dir", type=Path, default=Path("artifacts/quick-demo"))
    quick.add_argument("--ai-mode", choices=["mock", "real"], default="mock")
    return p


def execute(args, settings):
    from no2_madrid.pipeline import legacy_stage
    if args.command == "ingest":
        import pandas as pd
        start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
        if start > end:
            raise ValueError("--start debe ser anterior a --end.")
        source = args.source
        if source in {"all", "no2"}:
            legacy_stage(settings, "ingestion", "no2", ["--desde", str(start.year), "--hasta", str(end.year)])
        if source in {"municipal", "all"}:
            legacy_stage(settings, "ingestion", "meteorologia_municipal", ["--desde", str(start.year), "--hasta", str(end.year)])
        if source in {"all", "calendar"}:
            legacy_stage(settings, "ingestion", "work_calendar")
        if source in {"all", "metadata"} and settings.use_traffic:
            from no2_madrid.ingestion.metadata import ingest_metadata
            ingest_metadata(settings)
        if source in {"all", "traffic"} and settings.use_traffic:
            # El descargador histórico admite rango de años; la CLI filtra por fechas.
            from no2_madrid.ingestion import traffic
            links = traffic.obtener_enlaces()
            for (year, month), url in sorted(links.items()):
                if (start.year, start.month) <= (year, month) <= (end.year, end.month):
                    folder = settings.data_dir / "raw" / "traffic"
                    folder.mkdir(parents=True, exist_ok=True)
                    archive = folder / f"trafico_{year}_{month:02}.zip"
                    if not archive.exists() or args.refresh:
                        traffic.descargar_archivo(url, archive)
                    traffic.descomprimir_archivo(archive, folder / archive.stem)
    elif args.command == "preprocess":
        from no2_madrid.pipeline import preprocess
        preprocess(settings, args.workers)
    elif args.command == "build-dataset":
        from no2_madrid.dataset import build_dataset
        build_dataset(settings)
    elif args.command == "train":
        from no2_madrid.train import train
        report = train(settings, args.train_end, args.validation_end)
        print(json.dumps({"selected": report["selected"], "test": report["test"]["selected"]}, ensure_ascii=False))
    elif args.command in {"run", "predict"}:
        if args.command == "run":
            from no2_madrid.pipeline import run
            result = run(settings, args.date, args.prepare, args.workers)
        else:
            from no2_madrid.predict import predict
            result = predict(settings, args.date)
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if args.command == "demo":
            # No leer .env: demostración y CI siempre independientes de credenciales.
            from no2_madrid.demo import demo
            print(json.dumps(demo(args.dir), ensure_ascii=False, indent=2))
            return
        if args.command == "quick-demo":
            from no2_madrid.quick_demo import quick_demo
            print(json.dumps(quick_demo(args.dir, args.ai_mode), ensure_ascii=False, indent=2))
            return
        settings = Settings.from_env()
        overrides = {k: getattr(args, k) for k in ("data_dir", "output_dir") if getattr(args, k) is not None}
        if args.without_traffic:
            overrides["use_traffic"] = False
        if getattr(args, "ai_mode", None):
            overrides["ai_mode"] = args.ai_mode
        settings = replace(settings, **overrides)
        folder = settings.output_dir / "reports" / "runs"
        folder.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(folder / "pipeline.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        execute(args, settings)
    except (ValueError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        raise SystemExit(1) from None
    except Exception as exc:
        # Los errores de proveedores/red pueden contener credenciales; sólo se registra el tipo.
        logging.error("La etapa ha fallado (%s). Comprueba fuentes, conexión y configuración.", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
