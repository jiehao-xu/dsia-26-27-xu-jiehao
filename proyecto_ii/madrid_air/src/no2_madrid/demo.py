"""Ejemplo sintético determinista: nunca se mezcla con datos reales."""
from dataclasses import replace

import numpy as np
import pandas as pd

from no2_madrid.config import Settings
from no2_madrid.dataset import build_dataset
from no2_madrid.io import write_json
from no2_madrid.predict import predict
from no2_madrid.preprocess.common import guardar_csv
from no2_madrid.train import train


def make_demo(settings):
    days = pd.date_range("2023-01-01", "2026-03-31")
    rng = np.random.default_rng(settings.random_state)
    trend = np.arange(len(days))
    target = 30 + 12*np.cos(2*np.pi*trend/365) + 5*np.cos(2*np.pi*trend/7) + rng.normal(0, 2, len(days))
    no2 = pd.concat([pd.DataFrame({"FECHA": days, "ESTACION": station,
                        "NO2": (target+offset).clip(min=0), "VALIDO": 1})
                        for station, offset in [(4, -2), (8, 2)]], ignore_index=True)
    for year, group in no2.groupby(no2.FECHA.dt.year):
        guardar_csv(group, settings.process_dir / "no2" / f"calidad_aire_diario_{year}.csv")
    meteo = pd.DataFrame({"FECHA": days, "ESTACION": 4,
                          "PARAMETRO": "temperatura", "N_HORAS_VALIDAS": 24})
    for hour in range(1, 25):
        meteo[f"H{hour:02}"] = 15 - 10*np.cos(2*np.pi*trend/365)
    for year, group in meteo.groupby(meteo.FECHA.dt.year):
        guardar_csv(group, settings.process_dir / "meteorologia_municipal" / f"meteorologicos_horarios_{year}.csv")
    calendar = pd.DataFrame({"FECHA": pd.date_range(days.min(), days.max()+pd.Timedelta(days=1))})
    calendar["TIPO_DIA"] = calendar.FECHA.dt.day_of_week.map(
        {0:"laborable", 1:"laborable", 2:"laborable", 3:"laborable", 4:"laborable", 5:"sabado", 6:"domingo"})
    guardar_csv(calendar, settings.process_dir / "calendar" / "calendario_laboral.csv")
    write_json(settings.data_dir / "SYNTHETIC.json", {"synthetic": True, "seed": settings.random_state})


def demo(root):
    settings = Settings(data_dir=root / "data", output_dir=root, use_traffic=False)
    make_demo(settings)
    build_dataset(settings)
    train(settings)
    return predict(settings)
