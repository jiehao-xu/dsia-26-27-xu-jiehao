"""Descarga de recursos CSV del portal municipal con validación básica."""
from io import BytesIO
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session():
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=.5,
            status_forcelist=[429, 500, 502, 503, 504])))
    return s


def latest_csv(dataset, resource=None):
    url = f"https://datos.madrid.es/dataset/{dataset}/downloads"
    with session() as s:
        r = s.get(url, timeout=30)
        r.raise_for_status()
        links = [urljoin(url, a["href"]) for a in BeautifulSoup(r.content, "html.parser").select("a[href]")
                 if urlparse(a["href"]).path.lower().endswith(".csv")]
        if not links:
            raise ValueError(f"El portal no ofrece un CSV en {url}.")
        if resource:
            links = [link for link in links if f"/resource/{resource}/" in link]
            if not links:
                raise ValueError(f"No se encuentra el recurso acumulado {resource}.")
        def resource_number(link):
            match = re.search(r"/resource/\d+-(\d+)-", link)
            return int(match[1]) if match else -1
        source = max(links, key=resource_number)
        r = s.get(source, timeout=60)
        r.raise_for_status()
        if "html" in r.headers.get("Content-Type", "").lower():
            raise ValueError("El portal devolvió HTML en lugar de CSV.")
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                frame = pd.read_csv(BytesIO(r.content), sep=";", encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Codificación CSV no reconocida.")
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("CSV vacío o con formato inesperado.")
    return frame, source
