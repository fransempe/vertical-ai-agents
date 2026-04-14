"""Tests de integración (Supabase, OpenAI, etc.). Ejecutar explícitamente:

    pytest tests/integration -m integration --override-ini addopts='-q --strict-markers'

o desactivar el filtro por defecto en pyproject si preferís otro flujo.

Variables opcionales:

- ``CANDIDATE_EVAL_INTEGRATION_BASE_URL`` — base HTTP(S) de la API (p. ej. ``http://127.0.0.1:8000``).
- ``CANDIDATE_EVAL_INTEGRATION_BEARER_TOKEN`` — si el despliegue exige JWT u otro Bearer,
  se envía ``Authorization: Bearer <token>`` en los GET de smoke.
- ``CANDIDATE_EVAL_INTEGRATION_POST_SMOKE=1`` — además de la base URL, ejecuta un POST mínimo a
  ``/chatbot`` sin cuerpo válido para esperar **422** (validación) sin gastar OpenAI en el servidor
  (útil solo como contrato de ruta; si la API exige auth, combinar con Bearer).
- ``CANDIDATE_EVAL_INTEGRATION_CHATBOT_LIVE=1`` — además de la base URL, POST a ``/chatbot`` con
  JSON válido (``message`` + ``conversation_history``). Si el servidor responde **500** por falta de
  ``OPENAI_API_KEY`` u otro fallo de configuración, el test hace **skip** (no falla el contrato).
  El servidor debe tener las variables necesarias para la ruta de chatbot; no ejecutar en CI sin
  entorno preparado.
"""

import json
import os
import urllib.error
import urllib.request

import pytest


def _request_get_with_optional_bearer(url: str) -> urllib.request.Request:
    req = urllib.request.Request(url, method="GET")
    token = os.getenv("CANDIDATE_EVAL_INTEGRATION_BEARER_TOKEN", "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


def _request_post_json_with_optional_bearer(url: str, payload: dict) -> urllib.request.Request:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    token = os.getenv("CANDIDATE_EVAL_INTEGRATION_BEARER_TOKEN", "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


@pytest.mark.integration
def test_live_status_optional():
    base = os.getenv("CANDIDATE_EVAL_INTEGRATION_BASE_URL", "").strip()
    if not base:
        pytest.skip(
            "Opcional: export CANDIDATE_EVAL_INTEGRATION_BASE_URL=http://host:puerto "
            "para un smoke GET /status contra una instancia en ejecución"
        )
    url = base.rstrip("/") + "/status"
    try:
        req = _request_get_with_optional_bearer(url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            assert resp.status == 200
            body = resp.read()
            assert b"active" in body.lower() or b"status" in body.lower()
    except urllib.error.URLError as e:
        pytest.skip(f"No se pudo contactar la API en {url!r}: {e}")


@pytest.mark.integration
def test_live_openapi_docs_optional():
    """Smoke opcional: página Swagger (misma base URL que /status)."""
    base = os.getenv("CANDIDATE_EVAL_INTEGRATION_BASE_URL", "").strip()
    if not base:
        pytest.skip("Opcional: misma variable CANDIDATE_EVAL_INTEGRATION_BASE_URL que test_live_status_optional")
    url = base.rstrip("/") + "/docs"
    try:
        req = _request_get_with_optional_bearer(url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            assert resp.status == 200
            body = resp.read(8000)
            assert b"html" in body.lower() or b"openapi" in body.lower() or b"swagger" in body.lower()
    except urllib.error.URLError as e:
        pytest.skip(f"No se pudo GET /docs en {url!r}: {e}")


@pytest.mark.integration
def test_live_post_chatbot_validation_optional():
    """POST vacío a /chatbot → 422 (sin campo message), sin depender de OpenAI."""
    base = os.getenv("CANDIDATE_EVAL_INTEGRATION_BASE_URL", "").strip()
    if not base:
        pytest.skip("Requiere CANDIDATE_EVAL_INTEGRATION_BASE_URL")
    if os.getenv("CANDIDATE_EVAL_INTEGRATION_POST_SMOKE", "").strip() not in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("Opcional: export CANDIDATE_EVAL_INTEGRATION_POST_SMOKE=1 para intentar POST /chatbot")
    url = base.rstrip("/") + "/chatbot"
    req = _request_post_json_with_optional_bearer(url, {})
    try:
        urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as e:
        assert e.code == 422
    except urllib.error.URLError as e:
        pytest.skip(f"No se pudo POST /chatbot en {url!r}: {e}")


@pytest.mark.integration
def test_live_post_chatbot_valid_body_optional():
    """POST con cuerpo válido; si el servidor no tiene OpenAI, skip en lugar de fallar."""
    base = os.getenv("CANDIDATE_EVAL_INTEGRATION_BASE_URL", "").strip()
    if not base:
        pytest.skip("Requiere CANDIDATE_EVAL_INTEGRATION_BASE_URL")
    if os.getenv("CANDIDATE_EVAL_INTEGRATION_CHATBOT_LIVE", "").strip() not in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("Opcional: export CANDIDATE_EVAL_INTEGRATION_CHATBOT_LIVE=1 para POST /chatbot con message")
    url = base.rstrip("/") + "/chatbot"
    req = _request_post_json_with_optional_bearer(url, {"message": "ping", "conversation_history": []})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode())
            assert "response" in body
    except urllib.error.HTTPError as e:
        if e.code != 500:
            raise
        body = e.read().decode()
        try:
            err = json.loads(body)
            detail = str(err.get("detail", ""))
        except json.JSONDecodeError:
            detail = body
        if "openai" in detail.lower() or "OPENAI" in detail:
            pytest.skip("Servidor sin OPENAI_API_KEY o configuración para /chatbot (esperado en local)")
        raise
    except urllib.error.URLError as e:
        pytest.skip(f"No se pudo POST /chatbot en {url!r}: {e}")
