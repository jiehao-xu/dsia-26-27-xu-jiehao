"""Petición REST a Gemini: clave en cabecera, instrucciones y datos separados."""
from urllib.parse import quote

import httpx

from madrid_air.ai.client import AIServiceError


def generate_text(api_key: str, model: str, instructions: str, facts: str, max_output_tokens: int = 512) -> str:
    """Devuelve el texto de Gemini o un error sin revelar la clave ni la respuesta HTTP."""
    model_id = quote(model, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": facts}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_output_tokens},
    }
    # Este resumen no necesita razonamiento extenso. Se aplica solo a los
    # modelos comprobados, para no enviar opciones incompatibles a otros.
    if model in {"gemini-3.1-flash-lite", "gemini-3.5-flash-lite"}:
        body["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "minimal"}
    try:
        response = httpx.post(url, headers={"x-goog-api-key": api_key}, json=body, timeout=60)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise AIServiceError(
            f"Google rechazó la solicitud (HTTP {exc.response.status_code}). "
            "Revisa GOOGLE_API_KEY, permisos, cuota y GOOGLE_MODEL."
        ) from None
    except (httpx.HTTPError, ValueError) as exc:
        raise AIServiceError(f"No se pudo consultar Google ({type(exc).__name__}).") from None

    candidates = payload.get("candidates", [])
    if not candidates:
        raise AIServiceError("Google no devolvió una interpretación; la solicitud puede estar bloqueada.")
    candidate = candidates[0]
    if candidate.get("finishReason") != "STOP":
        raise AIServiceError("Google no completó la interpretación. No se guardará un texto truncado.")
    text_parts = []
    for part in candidate.get("content", {}).get("parts", []):
        if isinstance(part.get("text"), str) and not part.get("thought", False):
            text_parts.append(part["text"])
    text = "\n".join(text_parts).strip()
    if not text:
        raise AIServiceError("Google devolvió una interpretación vacía.")
    return text
