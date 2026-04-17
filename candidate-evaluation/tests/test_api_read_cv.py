"""POST /read-cv con crew y threadpool mockeados."""

import re

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app  # noqa: E402


class _FakeCrew:
    def kickoff(self):
        return '{"success": true, "email": "c@example.com"}'


class _FakeCrewRawAttr:
    def kickoff(self):
        class _R:
            raw = '{"success": true, "email": "c@example.com"}'

        return _R()


class _FakeCrewAlreadyExists:
    def kickoff(self):
        return '{"success": false, "error_type": "AlreadyExists"}'


class _FakeCrewFailedCreate:
    def kickoff(self):
        return '{"success": false}'


class _FakeCrewRaises:
    def kickoff(self):
        raise RuntimeError("crew boom")


def test_read_cv_success(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrew())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["filename"] == "folder/cv.pdf"
    assert data.get("candidate_status") == "created"
    assert data.get("candidate_created") is True


def test_read_cv_uses_result_raw_string(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewRawAttr())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    assert r.json().get("candidate_created") is True


def test_read_cv_candidate_already_exists_status(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewAlreadyExists())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("candidate_status") == "exists"
    assert "ya existía" in data.get("message", "").lower() or "existía" in data.get("message", "")


def test_read_cv_candidate_failed_status(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewFailedCreate())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("candidate_status") == "failed"
    assert "No se pudo crear" in data.get("message", "")


def test_read_cv_returns_500_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 500
    detail = r.json().get("detail", "")
    assert "Variables de entorno" in detail or "faltantes" in detail.lower()


def test_read_cv_kickoff_raises_returns_500(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewRaises())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 500
    assert "crew boom" in r.json().get("detail", "")


class _FakeCrewMultiJsonBlocks:
    """Varios `{...}` en el texto; se toma el último bloque con success/email (251–257)."""

    def kickoff(self):
        return (
            '{"noise": true} '
            '{"success": false, "error_type": "AlreadyExists"} '
            '{"success": true, "email": "last@block.example"}'
        )


def test_read_cv_picks_last_json_block_with_success_email(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewMultiJsonBlocks())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("candidate_created") is True
    assert data.get("candidate_status") == "created"


class _FakeCrewInvalidThenValidJson:
    """Primer bloque `{...}` inválido → `continue` (251–252); el siguiente parsea."""

    def kickoff(self):
        return '{"bad": } {"success": true, "email": "ok@example.com"}'


def test_read_cv_skips_invalid_json_block_then_uses_valid(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrewInvalidThenValidJson())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("candidate_created") is True
    assert data.get("candidate_status") == "created"


def test_read_cv_swallows_exception_in_candidate_json_parse_block(monkeypatch):
    """Si `re.findall` lanza, el `except` externo ignora (263–265)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *a, **k: _FakeCrew())

    async def _run_pool(fn):
        return fn()

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    def _boom(*_a, **_k):
        raise RuntimeError("findall boom")

    monkeypatch.setattr(re, "findall", _boom)
    client = TestClient(app)
    r = client.post("/read-cv", json={"filename": "folder/cv.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("candidate_result") is None
    assert data.get("candidate_created") is None
