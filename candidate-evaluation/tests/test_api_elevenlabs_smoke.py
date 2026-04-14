"""Rutas ElevenLabs: ramas tempranas sin llamar a APIs externas."""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

from api import app  # noqa: E402


def test_create_elevenlabs_agent_missing_env_returns_500(monkeypatch):
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    r = client.post(
        "/create-elevenlabs-agent",
        json={"jd_interview_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 500
    assert "Variables de entorno" in r.json()["detail"] or "faltantes" in r.json()["detail"].lower()


def test_update_elevenlabs_agent_missing_env_returns_500(monkeypatch):
    for key in ("SUPABASE_URL", "SUPABASE_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    r = client.patch(
        "/update-elevenlabs-agent",
        json={"jd_interview_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 500
