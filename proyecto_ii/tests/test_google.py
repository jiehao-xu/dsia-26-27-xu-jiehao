from unittest.mock import Mock

import httpx
import pytest

from madrid_air.ai.client import AIServiceError, ResultsClient
from test_ai import results


def google_response(monkeypatch, payload):
    response = Mock()
    response.json.return_value = payload
    post = Mock(return_value=response)
    monkeypatch.setattr("madrid_air.ai.google.httpx.post", post)
    return post, response


def test_google_uses_header_and_separate_instructions(monkeypatch):
    post, _ = google_response(monkeypatch, {"candidates": [{
        "finishReason": "STOP",
        "content": {"parts": [
            {"text": "internal", "thought": True}, {"text": "Interpretación de prueba."}
        ]},
    }]})
    answer = ResultsClient(mode="real", token="test-key", service="google",
                           provider="google", model="test-model").interpret(results())
    assert answer.provider == "google"
    assert answer.text == "Interpretación de prueba."
    request = post.call_args
    assert request.kwargs["headers"] == {"x-goog-api-key": "test-key"}
    assert "test-key" not in request.args[0]
    assert "test-key" not in str(request.kwargs["json"])
    facts = request.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert '"baseline_mae": 5.0' in facts
    assert '"mae_comparison": "mejora"' in facts
    assert "baseline_mae" in request.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert request.args[0].endswith("/test-model:generateContent")


@pytest.mark.parametrize("payload", [
    {}, {"candidates": []},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]},
])
def test_google_rejects_empty_or_incomplete_output(monkeypatch, payload):
    google_response(monkeypatch, payload)
    with pytest.raises(AIServiceError):
        ResultsClient(mode="real", token="test-key", service="google").interpret(results())


def test_google_http_error_does_not_reveal_key(monkeypatch):
    _, response = google_response(monkeypatch, {})
    error_response = httpx.Response(403, request=httpx.Request("POST", "https://example.org"))
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "secret test-key", request=error_response.request, response=error_response,
    )
    with pytest.raises(AIServiceError) as error:
        ResultsClient(mode="real", token="test-key", service="google").interpret(results())
    assert "403" in str(error.value)
    assert "test-key" not in str(error.value)


def test_google_environment_and_missing_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "google")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        ResultsClient.from_env("real")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_MODEL", "test-model")
    client = ResultsClient.from_env("real")
    assert client.service == "google"
    assert client.model == "test-model"
    assert ResultsClient.from_env("mock").interpret(results()).mode == "mock"


def test_google_timeout_does_not_expose_key_or_fall_back(monkeypatch):
    post, _ = google_response(monkeypatch, {})
    post.side_effect = httpx.ReadTimeout("private test-key")
    with pytest.raises(AIServiceError) as error:
        ResultsClient(mode="real", token="test-key").interpret(results())
    assert "test-key" not in str(error.value)
    assert "ReadTimeout" in str(error.value)


def test_flash_lite_limits_consumption(monkeypatch):
    post, _ = google_response(monkeypatch, {"candidates": [{
        "finishReason": "STOP", "content": {"parts": [{"text": "Resumen."}]},
    }]})
    monkeypatch.setenv("AI_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_MODEL", raising=False)
    client = ResultsClient.from_env("real")
    client.interpret(results())
    assert client.model == "gemini-3.1-flash-lite"
    generation = post.call_args.kwargs["json"]["generationConfig"]
    assert generation["maxOutputTokens"] == 512
    assert generation["thinkingConfig"]["thinkingLevel"] == "minimal"
    post.assert_called_once()
