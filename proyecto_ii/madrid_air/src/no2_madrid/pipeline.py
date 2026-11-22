"""Orquestación reutilizable desde CLI y futura API."""
import importlib
import logging
import sys
from time import monotonic

from no2_madrid.config import Settings

log = logging.getLogger(__name__)


def legacy_stage(settings, package, name, args=()):
    """Adapta las rutas de los módulos existentes conservando su CLI individual."""
    module = importlib.import_module(f"no2_madrid.{package}.{name}")
    previous_argv = sys.argv
    previous = {}
    for attr, value in {"RAW_DIR": settings.data_dir / "raw", "PROCESS_DIR": settings.process_dir,
                        "OUTPUT_DIR": settings.data_dir / "raw" / ({"work_calendar": "calendar"}.get(name, name))}.items():
        if hasattr(module, attr):
            previous[attr] = getattr(module, attr)
            setattr(module, attr, value)
    try:
        sys.argv = [f"{package}.{name}", *args]
        module.main()
    finally:
        sys.argv = previous_argv
        for attr, value in previous.items():
            setattr(module, attr, value)


def preprocess(settings: Settings, workers=1):
    for name in ("no2", "meteorologia_municipal", "work_calendar"):
        legacy_stage(settings, "preprocess", name)
    if settings.use_traffic:
        legacy_stage(settings, "preprocess", "traffic", ["--workers", str(workers)])


def run(settings: Settings, date=None, prepare=False, workers=1):
    from no2_madrid.dataset import build_dataset
    from no2_madrid.predict import predict
    start = monotonic()
    if prepare:
        preprocess(settings, workers)
    build_dataset(settings)
    result = predict(settings, date)
    log.info("Pipeline completado en %.2f s", monotonic()-start)
    return result
