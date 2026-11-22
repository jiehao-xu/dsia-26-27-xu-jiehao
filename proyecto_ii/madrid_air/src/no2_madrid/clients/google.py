"""Borde Google: clave explícita, timeout y reintentos limitados."""
from dataclasses import asdict
import json

from no2_madrid.clients.base import PredictionContext


class GoogleClient:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("AI_MODE=real necesita GOOGLE_API_KEY.")
        from google import genai
        from google.genai import types
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=20_000, retry_options=types.HttpRetryOptions(attempts=2)))
        self.model = model

    def explain(self, context: PredictionContext) -> str:
        from google.genai import types
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents="Resume estos datos de una predicción histórica de NO₂: " + json.dumps(asdict(context)),
                config=types.GenerateContentConfig(
                    system_instruction=("Escribe como máximo tres frases en español. Usa exclusivamente los datos recibidos. "
                        "El ámbito es Madrid: la media de las estaciones municipales, no una estación individual ni una media ponderada por población. No cambies el valor no2 ni la unidad µg/m³. No atribuyas causas, no apliques umbrales "
                        "sanitarios ni des recomendaciones de salud. Explica que es una estimación y que el MAE "
                        "histórico no es un intervalo de confianza. Indica las entradas ausentes."),
                    temperature=0, max_output_tokens=350),
            )
            if not response.text or not response.text.strip():
                raise ValueError("Respuesta de Google vacía.")
            return response.text.strip()
        finally:
            self.client.close()
