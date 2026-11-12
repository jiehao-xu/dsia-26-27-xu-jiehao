"""Cliente de interpretación con Google Gemini, y modo mock local.

sklearn hace los cálculos. Este cliente los convierte en una explicación breve.
El modo mock es una plantilla determinista para aprender y probar sin Internet.
"""
from dataclasses import asdict, dataclass
import json
import math
import os


GOOGLE_MODEL = "gemini-3.1-flash-lite"


@dataclass(frozen=True)
class ResultsContext:
    """Resumen numérico que recibe la IA; las métricas son del test histórico."""

    timestamp: str
    target_timestamp: str
    predicted_no2: float
    mae: float
    rmse: float
    baseline_mae: float
    baseline_rmse: float
    test_start: str
    test_end: str
    test_rows: int

    def __post_init__(self):
        values = [self.predicted_no2, self.mae, self.rmse, self.baseline_mae, self.baseline_rmse]
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("La predicción y los errores deben ser finitos y no negativos.")
        if self.test_rows < 1:
            raise ValueError("La evaluación debe contener al menos una fila.")

    @property
    def mae_comparison(self) -> str:
        """La comparación se calcula en Python: no se delega la aritmética al LLM."""
        if self.mae < self.baseline_mae:
            return "mejora"
        if self.mae > self.baseline_mae:
            return "empeora"
        return "iguala"


@dataclass(frozen=True)
class Interpretation:
    text: str
    mode: str
    provider: str
    model: str


class AIServiceError(RuntimeError):
    """Error del servicio remoto sin incluir credenciales ni detalles HTTP."""


class ResultsClient:
    def __init__(self, mode: str = "mock", token: str = "",
                 model: str = GOOGLE_MODEL, provider: str = "google",
                 service: str = "google") -> None:
        if mode not in {"mock", "real"}:
            raise ValueError("AI_MODE debe ser mock o real.")
        if service != "google":
            raise ValueError("AI_PROVIDER debe ser google.")
        if mode == "real" and not token.strip():
            key_name = "GOOGLE_API_KEY"
            raise ValueError(f"Falta {key_name}. Usa --ai-mode mock para probar sin token.")
        if not model.strip() or not provider.strip():
            raise ValueError("El modelo y el proveedor no pueden estar vacíos.")
        self.mode = mode
        self.model = model
        self.provider = provider
        self.service = service
        self._token = token

    @classmethod
    def from_env(cls, mode: str | None = None) -> "ResultsClient":
        """Settings.from_env carga .env antes de construir este cliente."""
        return cls(
            mode=mode if mode is not None else os.getenv("AI_MODE", "mock"),
            token=os.getenv("GOOGLE_API_KEY", ""),
            model=os.getenv("GOOGLE_MODEL", GOOGLE_MODEL),
            service=os.getenv("AI_PROVIDER", "google"),
        )

    def interpret(self, results: ResultsContext) -> Interpretation:
        """Explica la predicción y la calidad histórica, sin modificar las cifras."""
        if self.mode == "mock":
            text = (
                f"[MOCK: plantilla local] Se estiman {results.predicted_no2:.2f} microgramos/m3 "
                f"de NO2 para la hora que comienza en {results.target_timestamp}, "
                f"con origen en {results.timestamp}. Es una predicción, no una medición. "
                f"En las {results.test_rows} filas de test entre {results.test_start} y "
                f"{results.test_end}, el MAE del bosque fue {results.mae:.2f} y el de "
                f"persistencia {results.baseline_mae:.2f} microgramos/m3: el bosque "
                f"{results.mae_comparison} la referencia según MAE. "
                f"El RMSE fue {results.rmse:.2f}, frente a {results.baseline_rmse:.2f}. "
                "Persistencia supone que el NO2 de la siguiente hora será igual al de esta. "
                "Los errores son promedios históricos, no un intervalo de confianza "
                "de esta predicción. Estos datos no permiten atribuir causas."
            )
            return Interpretation(text, "mock", "local", "template-v1")

        facts = asdict(results)
        facts["mae_comparison"] = results.mae_comparison
        facts["station"] = "Escuelas Aguirre, Madrid"
        facts["unit"] = "microgramos/m3"
        messages = [
            {"role": "system", "content": (
                "Interpreta en español los resultados de un Random Forest que predice NO2. "
                "Escribe como máximo 100 palabras: predicción y evaluación. Usa exclusivamente "
                "las cifras, fechas y comparación recibidas; no recalcules ni alteres datos. "
                "Distingue la hora de origen y objetivo de la predicción del periodo histórico "
                "de evaluación. Explica MAE como error absoluto medio y RMSE como un error "
                "que penaliza más los fallos grandes. Persistencia predice que la siguiente "
                "hora será igual a la actual. Indica si el bosque mejora, iguala o empeora "
                "esa referencia según MAE, sin ocultar un resultado peor. No conviertas MAE "
                "ni RMSE en intervalos de confianza individuales. No inventes causas del "
                "tráfico o del tiempo, importancias de variables, alertas, límites legales "
                "o consejos sanitarios. No se proporcionan esos datos."
            )},
            {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
        ]
        return self.generate(messages[0]["content"], messages[1]["content"])

    def generate(self, instructions: str, facts: str, max_output_tokens: int = 512) -> Interpretation:
        """Una petición por informe; comparte transporte y errores entre ambos flujos."""
        if self.mode == "mock":
            return Interpretation("[MOCK: prueba local, sin llamada a la API]", "mock", "local", "template-v1")
        from madrid_air.ai.google import generate_text

        text = generate_text(
            self._token, self.model, instructions, facts,
            **({"max_output_tokens": max_output_tokens} if max_output_tokens != 512 else {}),
        )
        return Interpretation(text, "real", "google", self.model)
