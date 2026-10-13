import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def diccionario_epa():
    archivo = Path(__file__).resolve().parents[2] / "data" / "dr_EPA_2026.json"
    return json.loads(archivo.read_text(encoding="utf-8"))


@pytest.fixture
def personas_epa():
    return pd.DataFrame({
        "CCAA": ["01", "01", "13", "13", "13"],
        "SEXO1": ["1", "6", "1", "6", "1"],
        "NIVEL": ["1", "1", "1", "1", "2"],
        "EDAD1": ["20", "20", "20", "16", "10"],
        "NFORMA": ["S1", "SU", "P2", "S1", None],
        "CURSR": ["3", "3", "2", "3", None],
        "CURSNR": ["3", "3", "3", "3", None],
        "FACTOREL": ["100", "300", "200", "50", "25"],
    }, index=[2, 5, 9, 12, 15])
