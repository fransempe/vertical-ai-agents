"""GET /get-candidate-info y POST /chatbot (ramas ligeras)."""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app  # noqa: E402


def test_get_candidate_info_invalid_uuid_returns_error_status():
    client = TestClient(app)
    r = client.get("/get-candidate-info/not-a-valid-uuid")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert "uuid" in data["message"].lower()


def test_get_candidate_info_not_found(monkeypatch):
    uid = "550e8400-e29b-41d4-a716-446655440099"

    class _Limit:
        def execute(self):
            return type("R", (), {"data": []})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _SelectStar:
        def eq(self, *_a, **_k):
            return _Eq()

    class _CandTable:
        def select(self, _star):
            return _SelectStar()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    client = TestClient(app)
    r = client.get(f"/get-candidate-info/{uid}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_found"
    assert "no se encontró" in data["message"].lower()


def test_get_candidate_info_invalid_tech_stack_coerces_to_empty_skills(monkeypatch):
    uid = "550e8400-e29b-41d4-a716-446655440088"

    class _Limit:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": uid,
                            "name": "Bob",
                            "tech_stack": "not-a-list",
                            "observations": {"other": "freelance"},
                        }
                    ]
                },
            )()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _SelectStar:
        def eq(self, *_a, **_k):
            return _Eq()

    class _CandTable:
        def select(self, _star):
            return _SelectStar()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    client = TestClient(app)
    r = client.get(f"/get-candidate-info/{uid}")
    assert r.status_code == 200
    data = r.json()
    assert data["candidate"]["skills"] == []
    assert data["candidate"]["experience"] == "freelance"


def test_get_candidate_info_supabase_raises_returns_500(monkeypatch):
    monkeypatch.setattr(api_module, "get_supabase_client", lambda: (_ for _ in ()).throw(RuntimeError("db down")))

    client = TestClient(app)
    r = client.get("/get-candidate-info/550e8400-e29b-41d4-a716-446655440077")
    assert r.status_code == 500
    assert "db down" in r.json().get("detail", "")


def test_get_candidate_info_impl_reraises_http_exception(monkeypatch):
    """1675–1676: `HTTPException` interna no se convierte en 500 genérico."""
    from fastapi import HTTPException

    def _raise_http():
        raise HTTPException(status_code=418, detail="teapot")

    monkeypatch.setattr(api_module, "get_supabase_client", _raise_http)
    with pytest.raises(HTTPException) as exc_info:
        api_module._get_candidate_info_impl("550e8400-e29b-41d4-a716-446655440001", True)
    assert exc_info.value.status_code == 418
    assert exc_info.value.detail == "teapot"


def test_get_candidate_info_row_not_mapping_returns_500(monkeypatch):
    """Fila sin `.get` → excepción genérica 1677–1683."""

    class _Limit:
        def execute(self):
            class _Row:
                pass

            return type("R", (), {"data": [_Row()]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _SelectStar:
        def eq(self, *_a, **_k):
            return _Eq()

    class _CandTable:
        def select(self, _star):
            return _SelectStar()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    client = TestClient(app)
    r = client.get("/get-candidate-info/550e8400-e29b-41d4-a716-446655440088")
    assert r.status_code == 500
    detail = r.json().get("detail", "")
    assert "Error obteniendo" in detail or "candidato" in detail.lower()


def test_get_candidate_info_success(monkeypatch):
    uid = "550e8400-e29b-41d4-a716-446655440000"

    class _Limit:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": uid,
                            "name": "Ana",
                            "tech_stack": ["python"],
                            "observations": {"work_experience": [{"company": "ACME"}]},
                        }
                    ]
                },
            )()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _SelectStar:
        def eq(self, *_a, **_k):
            return _Eq()

    class _CandTable:
        def select(self, _star):
            return _SelectStar()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    client = TestClient(app)
    r = client.get(f"/get-candidate-info/{uid}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["candidate"]["name"] == "Ana"
    assert data["candidate"]["skills"] == ["python"]


def test_chatbot_returns_500_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "hola"})
    assert r.status_code == 500
    assert "OPENAI" in r.json()["detail"] or "openai" in r.json()["detail"].lower()
