"""Rutas GET /match-candidates/{run_id} (requiere importar api)."""

import uuid

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app, matching_runs  # noqa: E402


def test_match_candidates_status_404_when_unknown():
    client = TestClient(app)
    r = client.get("/match-candidates/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 404


def test_match_candidates_status_done():
    rid = "test-run-done"
    matching_runs[rid] = {"status": "done", "result": {"matches": []}}
    try:
        client = TestClient(app)
        r = client.get(f"/match-candidates/{rid}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done"
        assert body["result"] == {"matches": []}
    finally:
        matching_runs.pop(rid, None)


def test_match_candidates_status_error():
    rid = "test-run-err"
    matching_runs[rid] = {"status": "error", "error": "falló matching"}
    try:
        client = TestClient(app)
        r = client.get(f"/match-candidates/{rid}")
        assert r.status_code == 200
        assert r.json()["status"] == "error"
        assert "falló" in r.json()["error"]
    finally:
        matching_runs.pop(rid, None)


def test_match_candidates_status_queued():
    rid = "test-run-q"
    matching_runs[rid] = {"status": "queued", "progress": 0.0, "message": "en cola"}
    try:
        client = TestClient(app)
        r = client.get(f"/match-candidates/{rid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "queued"
        assert data["progress"] == 0.0
        assert data["message"] == "en cola"
    finally:
        matching_runs.pop(rid, None)


def test_match_candidates_post_returns_202(monkeypatch):
    def _noop_task(run_id, user_id, client_id):
        return None

    monkeypatch.setattr(api_module, "do_matching_long_task", _noop_task)
    client = TestClient(app)
    r = client.post("/match-candidates", json={})
    assert r.status_code == 202
    payload = r.json()
    assert "runId" in payload
    assert payload["status"] == "queued"
    rid = payload["runId"]
    try:
        assert rid in matching_runs
    finally:
        matching_runs.pop(rid, None)


def test_match_candidates_post_raises_500_when_thread_start_fails(monkeypatch):
    fixed = uuid.UUID("00000000-0000-0000-0000-000000000099")

    class _BadThread:
        def __init__(self, *_a, **_k):
            pass

        def start(self):
            raise RuntimeError("thread boom")

    monkeypatch.setattr(api_module.uuid, "uuid4", lambda: fixed)
    monkeypatch.setattr(api_module.threading, "Thread", lambda *a, **k: _BadThread())
    try:
        client = TestClient(app)
        r = client.post("/match-candidates", json={})
        assert r.status_code == 500
        detail = r.json().get("detail", "")
        assert "thread boom" in detail or "Error iniciando matching" in detail
    finally:
        matching_runs.pop(str(fixed), None)
