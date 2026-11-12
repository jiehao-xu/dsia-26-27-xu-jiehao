import json

import pandas as pd

from madrid_air.processing.common import numeric

WEATHER = {"tmed": "temperature", "hrMedia": "humidity", "velmedia": "wind_speed",
           "prec": "precipitation", "tmin": "temperature_min", "tmax": "temperature_max"}


def clean(path):
    """Convierte el JSON original en una tabla diaria, sin convertirla en horaria.

    WEATHER traduce nombres de la API a nombres del proyecto. Los campos que
    falten quedan vacíos; una ausencia no equivale a una temperatura de cero.
    """
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        content = path.read_text(encoding="cp1252")
    frame = pd.DataFrame(json.loads(content))
    result = pd.DataFrame({"date": pd.to_datetime(frame.fecha).dt.strftime("%Y-%m-%d")})
    for original, column in WEATHER.items():
        values = frame.get(original, pd.Series(index=frame.index, dtype="string"))
        result[column] = numeric(values.replace("Ip", "0"))
    return result.drop_duplicates("date", keep="last")
