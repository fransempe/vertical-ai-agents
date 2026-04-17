"""Smoke test del endpoint /status (importa el módulo api completo)."""

import pytest
from fastapi.testclient import TestClient


def test_get_status():
    try:
        from api import app
    except ModuleNotFoundError as e:
        pytest.skip(f"Dependencias de runtime no instaladas (pip install -r requirements.txt): {e}")

    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "active"
    assert "timestamp" in data
    assert data.get("service") == "Candidate Evaluation API"
