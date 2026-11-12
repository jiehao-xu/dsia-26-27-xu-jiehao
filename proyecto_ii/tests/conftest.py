"""Las pruebas no pueden abrir conexiones: todo servicio externo se simula."""
import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def reject_connection(*args, **kwargs):
        raise AssertionError("Los tests deben usar mocks, nunca conexiones de red.")

    monkeypatch.setattr(socket.socket, "connect", reject_connection)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_connection)
    monkeypatch.setenv("AI_MODE", "mock")
    monkeypatch.setenv("AI_PROVIDER", "google")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
