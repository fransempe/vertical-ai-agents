"""Tests unitarios para helpers de tools.supabase_tools."""

import json
import os
import re

import pytest
import requests

from tools import supabase_tools


class _DummyResponse:
    def __init__(self, status_code=200, headers=None, text="ok"):
        self.status_code = status_code
        self.headers = headers or {"content-type": "text/html"}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err


def test_fetch_url_with_retries_succeeds_after_timeout(monkeypatch):
    calls = {"n": 0}

    class _DummySession:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout, allow_redirects):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.exceptions.Timeout("boom")
            return _DummyResponse()

    monkeypatch.setattr(supabase_tools.requests, "Session", _DummySession)
    monkeypatch.setattr(supabase_tools.time, "sleep", lambda *_: None)

    out = supabase_tools._fetch_url_with_retries("https://example.com", max_retries=3)
    assert isinstance(out, _DummyResponse)
    assert calls["n"] == 2


def test_fetch_url_with_retries_raises_after_max_attempts(monkeypatch):
    class _DummySession:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout, allow_redirects):
            raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(supabase_tools.requests, "Session", _DummySession)
    monkeypatch.setattr(supabase_tools.time, "sleep", lambda *_: None)

    with pytest.raises(requests.exceptions.ConnectionError):
        supabase_tools._fetch_url_with_retries("https://example.com", max_retries=2)


def test_fetch_url_with_retries_raises_http_error_not_retried(monkeypatch):
    """`HTTPError` es `RequestException` pero no Timeout/ConnectionError → rama 53–54."""

    class _DummySession:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout, allow_redirects):
            err = requests.exceptions.HTTPError("bad")
            err.response = _DummyResponse(status_code=502, text="x")
            raise err

    monkeypatch.setattr(supabase_tools.requests, "Session", _DummySession)

    with pytest.raises(requests.exceptions.HTTPError):
        supabase_tools._fetch_url_with_retries("https://example.com", max_retries=3)


def test_fetch_url_with_retries_zero_attempts_raises_max_retries_message():
    """56: `range(0)` no entra al bucle → `RequestException` genérico."""
    with pytest.raises(requests.exceptions.RequestException, match="Máximo número de reintentos"):
        supabase_tools._fetch_url_with_retries("https://example.com", max_retries=0)


def test_fetch_job_description_invalid_url_returns_error_json():
    data = json.loads(supabase_tools.fetch_job_description.func("ftp://invalid"))
    assert data["success"] is False
    assert "URL no válida" in data["error"]


def test_fetch_job_description_empty_or_whitespace_returns_error():
    d0 = json.loads(supabase_tools.fetch_job_description.func(""))
    assert d0["success"] is False
    assert "vacía" in d0.get("error", "").lower() or "inválida" in d0.get("error", "").lower()
    dw = json.loads(supabase_tools.fetch_job_description.func("   \t  "))
    assert dw["success"] is False


def test_fetch_job_description_unexpected_error_from_helper(monkeypatch):
    """`except Exception` en fetch_job_description (172–174)."""
    monkeypatch.setattr(
        supabase_tools,
        "_fetch_url_with_retries",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fetch boom")),
    )
    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is False
    assert "Unexpected" in data.get("error", "") or "boom" in data.get("error", "").lower()


def test_fetch_job_description_unsupported_content_type(monkeypatch):
    def _fake_fetch(url, max_retries=3):
        return _DummyResponse(status_code=200, headers={"content-type": "application/pdf"}, text="binary")

    monkeypatch.setattr(supabase_tools, "_fetch_url_with_retries", _fake_fetch)

    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is False
    assert "no soportado" in data["error"]


def test_fetch_job_description_timeout_maps_to_error(monkeypatch):
    def _fake_fetch(url, max_retries=3):
        raise requests.exceptions.Timeout("slow")

    monkeypatch.setattr(supabase_tools, "_fetch_url_with_retries", _fake_fetch)

    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is False
    assert "Timeout" in data["error"]


def test_fetch_job_description_success_html(monkeypatch):
    monkeypatch.setattr(
        supabase_tools,
        "_fetch_url_with_retries",
        lambda url, max_retries=3: _DummyResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body>JD</body></html>",
        ),
    )
    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is True
    assert "JD" in data["content"]
    assert data["status_code"] == 200


def test_fetch_job_description_success_plain_text(monkeypatch):
    monkeypatch.setattr(
        supabase_tools,
        "_fetch_url_with_retries",
        lambda url, max_retries=3: _DummyResponse(
            status_code=200,
            headers={"content-type": "text/plain"},
            text="plain jd",
        ),
    )
    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd.txt"))
    assert data["success"] is True
    assert data["content"] == "plain jd"


def test_fetch_job_description_http_error(monkeypatch):
    def _fake_fetch(url, max_retries=3):
        resp = _DummyResponse(status_code=502, headers={}, text="bad")
        err = requests.exceptions.HTTPError("upstream")
        err.response = resp
        raise err

    monkeypatch.setattr(supabase_tools, "_fetch_url_with_retries", _fake_fetch)

    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is False
    assert "502" in data["error"]


def test_fetch_job_description_request_exception_returns_error(monkeypatch):
    def _boom(url, max_retries=3):
        raise requests.exceptions.RequestException("network glitch")

    monkeypatch.setattr(supabase_tools, "_fetch_url_with_retries", _boom)
    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data.get("success") is False
    assert "network glitch" in data.get("error", "") or "Error fetching" in data.get("error", "")


def test_fetch_job_description_connection_error(monkeypatch):
    def _fake_fetch(url, max_retries=3):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(supabase_tools, "_fetch_url_with_retries", _fake_fetch)

    data = json.loads(supabase_tools.fetch_job_description.func("https://example.com/jd"))
    assert data["success"] is False
    assert "conexión" in data["error"].lower() or "conectar" in data["error"].lower()


def test_extract_supabase_conversations_maps_rows(monkeypatch):
    rows = [
        {
            "meet_id": "m1",
            "candidate_id": "c1",
            "conversation_data": {"turns": []},
            "candidates": {
                "id": "id1",
                "name": "Ana",
                "email": "a@a.com",
                "phone": "1",
                "cv_url": "http://cv",
                "tech_stack": "py",
            },
        },
        {
            "meet_id": "m2",
            "candidate_id": "c2",
            "conversation_data": {},
            "candidates": None,
        },
    ]

    class _Select:
        def __init__(self, data):
            self._data = data

        def limit(self, n):
            return self

        def execute(self):
            return type("Resp", (), {"data": self._data})()

    class _Table:
        def __init__(self, data):
            self._data = data

        def select(self, _query):
            return _Select(self._data)

    class _Client:
        def table(self, name):
            assert name == "conversations"
            return _Table(rows)

    monkeypatch.setattr(supabase_tools, "create_client", lambda url, key: _Client())

    out = json.loads(supabase_tools.extract_supabase_conversations.func(10))
    assert len(out) == 2
    assert out[0]["meet_id"] == "m1"
    assert out[0]["candidate"]["name"] == "Ana"
    assert out[1]["candidate"]["name"] is None


def test_extract_supabase_conversations_returns_error_json_on_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(
        supabase_tools,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("conversations down")),
    )
    out = json.loads(supabase_tools.extract_supabase_conversations.func(5))
    assert "error" in out
    assert "conversations down" in out.get("error", "").lower() or "extracting" in out.get("error", "").lower()


def test_supabase_extractor_tool_inits_with_create_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    stub = object()

    def _cc(u, k):
        assert u == "http://local.test"
        return stub

    monkeypatch.setattr(supabase_tools, "create_client", _cc)
    tool = supabase_tools.SupabaseExtractorTool()
    assert tool.supabase is stub


def test_get_current_date_returns_json_with_slash_format():
    data = json.loads(supabase_tools.get_current_date.func())
    assert "current_date" in data
    assert "/" in data["current_date"]
    assert data.get("date_format") == "DD/MM/YYYY"


def test_get_current_date_exception_returns_fallback(monkeypatch):
    class _BadDateTime:
        @staticmethod
        def now():
            raise RuntimeError("clock")

    monkeypatch.setattr(supabase_tools, "datetime", _BadDateTime)
    data = json.loads(supabase_tools.get_current_date.func())
    assert "error" in data
    assert data.get("fallback_date") == "18/01/2025"


def test_get_meet_evaluation_data_meet_not_found(monkeypatch):
    class _MeetEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetSelect:
        def eq(self, *_a, **_k):
            return _MeetEq()

    class _MeetTableNF:
        def select(self, _q):
            return _MeetSelect()

    class _Client:
        def table(self, name):
            assert name == "meets"
            return _MeetTableNF()

    monkeypatch.setattr(supabase_tools, "create_client", lambda url, key: _Client())
    out = json.loads(supabase_tools.get_meet_evaluation_data.func("00000000-0000-0000-0000-000000000099"))
    assert "error" in out


def test_get_meet_evaluation_data_success(monkeypatch):
    meet_row = {
        "id": "m1",
        "jd_interviews_id": "jd1",
        "created_at": "c",
        "updated_at": "u",
        "jd_interviews": {
            "id": "jd1",
            "interview_name": "Dev",
            "agent_id": "a1",
            "job_description": "https://jd",
            "client_id": "cl1",
            "created_at": "cj",
        },
    }
    conv_row = {
        "meet_id": "m1",
        "candidate_id": "c1",
        "conversation_data": {"x": 1},
        "emotion_analysis": None,
        "candidates": {
            "id": "c1",
            "name": "Bo",
            "email": "b@b.com",
            "phone": "9",
            "cv_url": "http://cv",
            "tech_stack": "go",
        },
    }
    client_row = {"id": "cl1", "name": "ACME", "email": "client@acme.com"}

    class _ClientEq:
        def execute(self):
            return type("R", (), {"data": [client_row]})()

    class _ClientSelect:
        def eq(self, *_a, **_k):
            return _ClientEq()

    class _ConvLimit:
        def execute(self):
            return type("R", (), {"data": [conv_row]})()

    class _ConvOrder:
        def limit(self, _n):
            return _ConvLimit()

    class _ConvEq:
        def order(self, *_a, **kwargs):
            return _ConvOrder()

    class _ConvSelect:
        def eq(self, *_a, **_k):
            return _ConvEq()

    class _MeetEq:
        def execute(self):
            return type("R", (), {"data": [meet_row]})()

    class _MeetSelect:
        def eq(self, *_a, **_k):
            return _MeetEq()

    class _MeetTable:
        def select(self, _q):
            return _MeetSelect()

    class _ConvTable:
        def select(self, _q):
            return _ConvSelect()

    class _ClientsTable:
        def select(self, _q):
            return _ClientSelect()

    class _Client:
        def table(self, name):
            if name == "meets":
                return _MeetTable()
            if name == "conversations":
                return _ConvTable()
            if name == "clients":
                return _ClientsTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda url, key: _Client())
    monkeypatch.setenv("REPORT_TO_EMAIL", "")
    out = json.loads(supabase_tools.get_meet_evaluation_data.func("m1"))
    assert out["meet"]["id"] == "m1"
    assert out["conversation"]["candidate"]["name"] == "Bo"
    assert out["jd_interview"]["id"] == "jd1"
    assert out["client"]["email"] == "client@acme.com"


def test_get_meet_evaluation_data_empty_client_sets_fallback_report_email(monkeypatch):
    """797–801: sin filas en `clients` → fallback en `REPORT_TO_EMAIL`."""
    meet_row = {
        "id": "m1",
        "jd_interviews_id": "jd1",
        "created_at": "c",
        "updated_at": "u",
        "jd_interviews": {
            "id": "jd1",
            "interview_name": "Dev",
            "agent_id": "a1",
            "job_description": "https://jd",
            "client_id": "cl1",
            "created_at": "cj",
        },
    }
    conv_row = {
        "meet_id": "m1",
        "candidate_id": "c1",
        "conversation_data": {},
        "emotion_analysis": None,
        "candidates": None,
    }

    class _ClientEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _ClientSelect:
        def eq(self, *_a, **_k):
            return _ClientEq()

    class _ConvLimit:
        def execute(self):
            return type("R", (), {"data": [conv_row]})()

    class _ConvOrder:
        def limit(self, _n):
            return _ConvLimit()

    class _ConvEq:
        def order(self, *_a, **kwargs):
            return _ConvOrder()

    class _ConvSelect:
        def eq(self, *_a, **_k):
            return _ConvEq()

    class _MeetEq:
        def execute(self):
            return type("R", (), {"data": [meet_row]})()

    class _MeetSelect:
        def eq(self, *_a, **_k):
            return _MeetEq()

    class _MeetTable:
        def select(self, _q):
            return _MeetSelect()

    class _ConvTable:
        def select(self, _q):
            return _ConvSelect()

    class _ClientsTable:
        def select(self, _q):
            return _ClientSelect()

    class _Client:
        def table(self, name):
            if name == "meets":
                return _MeetTable()
            if name == "conversations":
                return _ConvTable()
            if name == "clients":
                return _ClientsTable()
            raise AssertionError(name)

    monkeypatch.setenv("REPORT_TO_EMAIL", "")
    monkeypatch.setattr(supabase_tools, "create_client", lambda url, key: _Client())
    out = json.loads(supabase_tools.get_meet_evaluation_data.func("m1"))
    assert out["conversation"] is not None
    assert os.environ.get("REPORT_TO_EMAIL") == "flocklab.id@gmail.com"


def test_get_meet_evaluation_data_jd_interviews_none_returns_error(monkeypatch):
    """792–845: `jd_interviews` ausente rompe la cadena → `except` externo."""
    meet_row = {
        "id": "m1",
        "jd_interviews_id": "jd1",
        "created_at": "c",
        "updated_at": "u",
        "jd_interviews": None,
    }

    class _MeetEq:
        def execute(self):
            return type("R", (), {"data": [meet_row]})()

    class _MeetSelect:
        def eq(self, *_a, **_k):
            return _MeetEq()

    class _MeetTable:
        def select(self, _q):
            return _MeetSelect()

    class _Client:
        def table(self, name):
            assert name == "meets"
            return _MeetTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda url, key: _Client())
    out = json.loads(supabase_tools.get_meet_evaluation_data.func("m1"))
    assert "error" in out


def test_save_meet_evaluation_missing_supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    out = json.loads(supabase_tools.save_meet_evaluation.func("{}"))
    assert "error" in out


def test_save_meet_evaluation_invalid_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: object())
    out = json.loads(supabase_tools.save_meet_evaluation.func("not-json"))
    assert out["success"] is False


def test_save_meet_evaluation_wrong_type(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: object())
    out = json.loads(supabase_tools.save_meet_evaluation.func(99))  # type: ignore[arg-type]
    assert out["success"] is False
    assert "string o dict" in out["error"].lower()


def test_save_meet_evaluation_missing_meet_id(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: object())
    payload = json.dumps({"candidate": {"id": "c"}, "jd_interview": {"id": "j"}})
    out = json.loads(supabase_tools.save_meet_evaluation.func(payload))
    assert out["success"] is False
    assert "meet_id" in out["error"].lower()


def test_save_meet_evaluation_insert_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _InsertExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-1"}]})()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def insert(self, _row):
            return _InsertExec()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {"technical_assessment": {"knowledge_level": "Alto"}},
        "match_evaluation": {"score": 1},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is True
    assert out["evaluation_id"] == "eval-1"
    assert out.get("action") == "created"


def test_save_meet_evaluation_update_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-existing"}]})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _UpdateEq:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-existing"}]})()

    class _MeetEvalUpdate:
        def eq(self, *_a, **_k):
            return _UpdateEq()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def update(self, _row):
            return _MeetEvalUpdate()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is True
    assert out["evaluation_id"] == "eval-existing"
    assert out.get("action") == "updated"


def test_save_meet_evaluation_update_returns_empty_data_fails(monkeypatch):
    """Rama 1013–1018: update sin filas en respuesta."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-u1"}]})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _UpdateEqEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalUpdate:
        def eq(self, *_a, **_k):
            return _UpdateEqEmpty()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def update(self, _row):
            return _MeetEvalUpdate()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is False
    assert "actualizando" in out.get("error", "").lower()


def test_save_meet_evaluation_insert_returns_empty_data_fails(monkeypatch):
    """Rama 1032–1037: insert sin filas."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _InsertExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def insert(self, _row):
            return _InsertExecEmpty()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is False
    assert "insertando" in out.get("error", "").lower() or "vacía" in out.get("error", "").lower()


def test_save_meet_evaluation_requires_candidate_id(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: object())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is False
    assert "candidate" in out.get("error", "").lower()


def test_save_meet_evaluation_requires_jd_interview_id(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: object())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is False
    assert "jd_interview" in out.get("error", "").lower()


def test_save_meet_evaluation_full_result_dict_branch(monkeypatch):
    """873–884: `full_result` ya es dict (sin `json.loads`)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _InsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "me-dict"}]})()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def insert(self, _row):
            return _InsExec()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {
            "technical_assessment": {
                "completeness_summary": "not-a-dict",
                "alerts": "not-a-list",
            },
        },
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(payload))  # type: ignore[arg-type]
    assert out["success"] is True
    assert out.get("evaluation_id") == "me-dict"


def test_save_meet_evaluation_technical_assessment_not_dict_normalized(monkeypatch):
    """937–938, 947–954: tipos no dict/list se normalizan."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _SelEq:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEvalSelect:
        def eq(self, *_a, **_k):
            return _SelEq()

    class _InsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "me-norm"}]})()

    class _MeetEvalTable:
        def select(self, _cols):
            return _MeetEvalSelect()

        def insert(self, _row):
            return _InsExec()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {"technical_assessment": "bad-not-dict"},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is True


def test_save_meet_evaluation_outer_exception_on_meet_eval_select(monkeypatch):
    """1039–1046: excepción no capturada en el flujo principal."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _MeetEvalTable:
        def select(self, _cols):
            raise RuntimeError("meet_eval boom")

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _MeetEvalTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    payload = {
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "candidate": {"id": "550e8400-e29b-41d4-a716-446655440001"},
        "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002"},
        "conversation_analysis": {},
        "match_evaluation": {},
    }
    out = json.loads(supabase_tools.save_meet_evaluation.func(json.dumps(payload)))
    assert out["success"] is False
    assert "meet_eval boom" in out.get("error", "")


def test_get_client_email_missing_supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    out = json.loads(supabase_tools.get_client_email.func("any-id"))
    assert "error" in out


def test_get_client_email_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Limit:
        def execute(self):
            return type("R", (), {"data": [{"id": "cl1", "email": "x@y.com", "name": "Cliente"}]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _ClientsSelect:
        def eq(self, *_a, **_k):
            return _Eq()

    class _ClientsTable:
        def select(self, _cols):
            return _ClientsSelect()

    class _Sb:
        def table(self, name):
            assert name == "clients"
            return _ClientsTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_client_email.func("cl1"))
    assert out["email"] == "x@y.com"
    assert out["name"] == "Cliente"


def test_get_client_email_not_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Limit:
        def execute(self):
            return type("R", (), {"data": []})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _ClientsSelect:
        def eq(self, *_a, **_k):
            return _Eq()

    class _ClientsTable:
        def select(self, _cols):
            return _ClientsSelect()

    class _Sb:
        def table(self, name):
            return _ClientsTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_client_email.func("missing"))
    assert "error" in out


def test_get_client_email_exception_returns_json_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(
        supabase_tools,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("supabase down")),
    )
    out = json.loads(supabase_tools.get_client_email.func("550e8400-e29b-41d4-a716-446655440001"))
    assert "error" in out
    assert "supabase down" in out["error"]


def test_get_client_email_row_without_email(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Limit:
        def execute(self):
            return type("R", (), {"data": [{"id": "cl1", "email": None, "name": "Sin mail"}]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _ClientsSelect:
        def eq(self, *_a, **_k):
            return _Eq()

    class _ClientsTable:
        def select(self, _cols):
            return _ClientsSelect()

    class _Sb:
        def table(self, name):
            return _ClientsTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_client_email.func("cl1"))
    assert "error" in out


def test_get_jd_interviews_data_missing_supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    out = json.loads(supabase_tools.get_jd_interviews_data.func("any-id"))
    assert "error" in out


def test_get_jd_interviews_data_by_id_empty(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Limit:
        def execute(self):
            return type("R", (), {"data": []})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _Sel:
        def eq(self, *_a, **_k):
            return _Eq()

    class _JdTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    raw = supabase_tools.get_jd_interviews_data.func("00000000-0000-0000-0000-000000000099")
    out = json.loads(raw)
    assert out == []


def test_get_jd_interviews_data_by_id_returns_row(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440000"

    row = {
        "id": jid,
        "interview_name": "Dev",
        "agent_id": "a1",
        "job_description": "desc",
        "client_id": "c1",
        "created_at": "t",
    }

    class _Limit:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _Sel:
        def eq(self, *_a, **_k):
            return _Eq()

    class _JdTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_jd_interviews_data.func(jid))
    assert len(out) == 1
    assert out[0]["interview_name"] == "Dev"


def test_get_jd_interviews_data_truncates_long_job_description(monkeypatch):
    """Rama que acota `job_desc` cuando len > 5000 (526–527)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400bd"
    long_jd = "J" * 6000
    row = {
        "id": jid,
        "interview_name": "Long JD",
        "agent_id": "a1",
        "job_description": long_jd,
        "client_id": "c1",
        "created_at": "t",
    }

    class _Limit:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _Sel:
        def eq(self, *_a, **_k):
            return _Eq()

    class _JdTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_jd_interviews_data.func(jid))
    assert len(out) == 1
    assert len(row["job_description"]) > 5000


def test_get_jd_interviews_data_warns_when_json_over_100k_chars(monkeypatch, capsys):
    """Aviso si `result_json` supera 100000 caracteres (545–547)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400be"
    huge_field = "H" * 200000
    row = {
        "id": jid,
        "interview_name": "Big",
        "agent_id": "a1",
        "job_description": huge_field,
        "client_id": "c1",
        "created_at": "t",
    }

    class _Limit:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _Eq:
        def limit(self, _n):
            return _Limit()

    class _Sel:
        def eq(self, *_a, **_k):
            return _Eq()

    class _JdTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    json.loads(supabase_tools.get_jd_interviews_data.func(jid))
    err = capsys.readouterr().out
    assert "ADVERTENCIA" in err or "grande" in err.lower() or "100000" in err or "chars" in err.lower()


def test_get_jd_interviews_data_active_listing_limit_50(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    row = {
        "id": "550e8400-e29b-41d4-a716-4466554400aa",
        "interview_name": "Active JD",
        "agent_id": "a1",
        "job_description": "desc",
        "client_id": "c1",
        "created_at": "t",
        "status": "active",
    }

    class _Limit:
        def __init__(self):
            self.n = None

        def limit(self, n):
            self.n = n
            return self

        def execute(self):
            assert self.n == 50
            return type("R", (), {"data": [row]})()

    class _Eq:
        def eq(self, col, val):
            assert col == "status" and val == "active"
            return _Limit()

    class _JdTable:
        def select(self, _star):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_jd_interviews_data.func(None))
    assert len(out) == 1
    assert out[0]["interview_name"] == "Active JD"


def test_get_jd_interviews_data_execute_raises_returns_error_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Exec:
        def execute(self):
            raise RuntimeError("supabase down")

    class _Lim:
        def limit(self, _n):
            return _Exec()

    class _Eq:
        def eq(self, *_a, **_k):
            return _Lim()

    class _JdTable:
        def select(self, _star):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_jd_interviews_data.func("550e8400-e29b-41d4-a716-446655440001"))
    assert "error" in out
    assert "supabase down" in out.get("error", "") or "Error obteniendo" in out.get("error", "")


def test_create_candidate_inserts_and_skips_index_errors(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    inserted = {
        "id": "cand-new-1",
        "name": "Nuevo",
        "email": "nuevo.unique@test.example",
    }

    class _InsertExec:
        def execute(self):
            return type("R", (), {"data": [inserted]})()

    class _CandTable:
        def select(self, *_a):
            return _EmptySelect()

        def insert(self, _p):
            return _InsertExec()

    class _EmptySelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())

    def _boom(_row):
        raise RuntimeError("index offline")

    monkeypatch.setattr(vector_tools, "index_candidate", _boom)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "Nuevo",
            "nuevo.unique@test.example",
            "555",
            "https://cv.example/x.pdf",
            "Python, Docker",
        )
    )
    assert out["success"] is True
    assert out["data"][0]["id"] == "cand-new-1"


def test_create_candidate_returns_already_exists_when_email_duplicate(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    existing = {
        "id": "550e8400-e29b-41d4-a716-446655440050",
        "email": "dup.only@test.example",
        "name": "Existente",
    }

    class _DupSelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [existing]})()

    class _CandTable:
        def select(self, *_a):
            return _DupSelect()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())

    out = json.loads(
        supabase_tools.create_candidate.func(
            "Otro",
            "dup.only@test.example",
            "1",
            "http://cv",
            "Go",
        )
    )
    assert out["success"] is False
    assert out.get("error_type") == "AlreadyExists"
    assert out["existing"]["id"] == existing["id"]


def test_create_candidate_inserts_candidate_recruiters_when_ids_given(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    uid = "550e8400-e29b-41d4-a716-446655440060"
    cid = "550e8400-e29b-41d4-a716-446655440061"
    inserted_row = {
        "id": "550e8400-e29b-41d4-a716-446655440062",
        "email": "recruiter.path@test.example",
        "name": "Rec",
    }
    recorded_recruiter = []

    class _RecIns:
        def execute(self):
            return type("R", (), {"data": [{"id": "cr1"}]})()

    class _RecTable:
        def insert(self, payload):
            recorded_recruiter.append(payload)
            return _RecIns()

    class _CandIns:
        def execute(self):
            return type("R", (), {"data": [inserted_row]})()

    class _EmptyEmailSelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _CandTable:
        def select(self, *_a):
            return _EmptyEmailSelect()

        def insert(self, _p):
            return _CandIns()

    class _Sb:
        def table(self, name):
            if name == "candidates":
                return _CandTable()
            if name == "candidate_recruiters":
                return _RecTable()
            raise AssertionError(name)

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "Rec",
            "recruiter.path@test.example",
            "555",
            "https://cv.example/r.pdf",
            "Rust",
            user_id=uid,
            client_id=cid,
        )
    )
    assert out["success"] is True
    assert len(recorded_recruiter) == 1
    assert recorded_recruiter[0]["candidate_id"] == inserted_row["id"]
    assert recorded_recruiter[0]["user_id"] == uid
    assert recorded_recruiter[0]["client_id"] == cid


def test_create_candidate_tech_stack_json_list_and_scalar_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    captured = []

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "c1", "email": "list.json@test.example"}]})()

    class _CandTable:
        def select(self, *_a):
            return _EmptySelect()

        def insert(self, payload):
            captured.append(payload)
            return _Ins()

    class _EmptySelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "L",
            "list.json@test.example",
            "1",
            "http://cv",
            '["Python", " Go "]',
        )
    )
    assert out["success"] is True
    assert captured[0]["tech_stack"] == ["Python", "Go"]

    captured.clear()
    out2 = json.loads(
        supabase_tools.create_candidate.func(
            "S",
            "scalar.json@test.example",
            "1",
            "http://cv",
            "42",
        )
    )
    assert out2["success"] is True
    assert captured[0]["tech_stack"] == ["42"]


def test_create_candidate_observations_bad_json_and_bad_type(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "c-obs", "email": "obs.bad@test.example"}]})()

    class _CandTable:
        def select(self, *_a):
            return _EmptySelect()

        def insert(self, payload):
            assert payload["observations"] is None
            return _Ins()

    class _EmptySelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "O",
            "obs.bad@test.example",
            "1",
            "http://cv",
            "Go",
            observations="{not json",
        )
    )
    assert out["success"] is True

    out2 = json.loads(
        supabase_tools.create_candidate.func(
            "O2",
            "obs.type@test.example",
            "1",
            "http://cv",
            "Go",
            observations=123,
        )
    )
    assert out2["success"] is True


def test_create_candidate_email_precheck_raises_still_inserts(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Sel:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            raise RuntimeError("supabase select down")

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "c-precheck", "email": "precheck@test.example"}]})()

    class _CandTable:
        def select(self, *_a):
            return _Sel()

        def insert(self, _p):
            return _Ins()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "P",
            "precheck@test.example",
            "1",
            "http://cv",
            "Rust",
        )
    )
    assert out["success"] is True
    assert out["data"][0]["id"] == "c-precheck"


def test_create_candidate_invalid_email_inserts_without_precheck(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    insert_calls = []

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "c-inv", "email": None}]})()

    class _CandTable:
        def insert(self, payload):
            insert_calls.append(payload)
            return _Ins()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "I",
            "not-an-email",
            "1",
            "http://cv",
            "Go",
        )
    )
    assert out["success"] is True
    assert len(insert_calls) == 1
    assert insert_calls[0]["email"] == "not-an-email"


def test_create_candidate_recruiter_insert_empty_data_logs(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    uid = "550e8400-e29b-41d4-a716-446655440070"
    cid = "550e8400-e29b-41d4-a716-446655440071"
    inserted_row = {
        "id": "550e8400-e29b-41d4-a716-446655440072",
        "email": "rec.empty@test.example",
        "name": "E",
    }

    class _RecIns:
        def execute(self):
            return type("R", (), {"data": []})()

    class _RecTable:
        def insert(self, _p):
            return _RecIns()

    class _CandIns:
        def execute(self):
            return type("R", (), {"data": [inserted_row]})()

    class _EmptyEmailSelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _CandTable:
        def select(self, *_a):
            return _EmptyEmailSelect()

        def insert(self, _p):
            return _CandIns()

    class _Sb:
        def table(self, name):
            if name == "candidates":
                return _CandTable()
            if name == "candidate_recruiters":
                return _RecTable()
            raise AssertionError(name)

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "E",
            "rec.empty@test.example",
            "1",
            "http://cv",
            "Go",
            user_id=uid,
            client_id=cid,
        )
    )
    assert out["success"] is True


def test_create_candidate_recruiter_insert_raises_still_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    uid = "550e8400-e29b-41d4-a716-446655440080"
    cid = "550e8400-e29b-41d4-a716-446655440081"
    inserted_row = {
        "id": "550e8400-e29b-41d4-a716-446655440082",
        "email": "rec.err@test.example",
        "name": "E2",
    }

    class _RecTable:
        def insert(self, _p):
            class _X:
                def execute(self):
                    raise RuntimeError("recruiter fk")

            return _X()

    class _CandIns:
        def execute(self):
            return type("R", (), {"data": [inserted_row]})()

    class _EmptyEmailSelect:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _CandTable:
        def select(self, *_a):
            return _EmptyEmailSelect()

        def insert(self, _p):
            return _CandIns()

    class _Sb:
        def table(self, name):
            if name == "candidates":
                return _CandTable()
            if name == "candidate_recruiters":
                return _RecTable()
            raise AssertionError(name)

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "E2",
            "rec.err@test.example",
            "1",
            "http://cv",
            "Go",
            user_id=uid,
            client_id=cid,
        )
    )
    assert out["success"] is True


def test_create_candidate_create_client_raises_returns_error_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    def _boom(_u, _k):
        raise RuntimeError("no supabase")

    monkeypatch.setattr(supabase_tools, "create_client", _boom)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "X",
            "fail@test.example",
            "1",
            "http://cv",
            "Go",
        )
    )
    assert out["success"] is False
    assert "no supabase" in out.get("error", "")


def test_save_interview_evaluation_jd_not_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f0"

    class _Lim:
        def execute(self):
            return type("R", (), {"data": []})()

    class _Eq:
        def limit(self, _n):
            return _Lim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            '{"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"}',
            "{}",
            "[]",
        )
    )
    assert out["success"] is False
    assert "No se encontró jd_interview" in out.get("error", "")


def test_save_interview_evaluation_client_id_null(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f1"

    class _Lim:
        def execute(self):
            row = {"id": jid, "client_id": None, "interview_name": "X"}
            return type("R", (), {"data": [row]})()

    class _Eq:
        def limit(self, _n):
            return _Lim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            '{"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"}',
            "{}",
            "[]",
        )
    )
    assert out["success"] is False
    assert "client_id" in out.get("error", "").lower()


def test_save_interview_evaluation_invalid_summary_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f2"

    class _Lim:
        def execute(self):
            row = {
                "id": jid,
                "client_id": "550e8400-e29b-41d4-a716-4466554400f3",
                "interview_name": "J",
            }
            return type("R", (), {"data": [row]})()

    class _Eq:
        def limit(self, _n):
            return _Lim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            "{ not valid json",
            "{}",
            "[]",
        )
    )
    assert out["success"] is False
    assert "parse" in out.get("error", "").lower() or "json" in out.get("error", "").lower()


def test_save_interview_evaluation_insert_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f4"
    cid = "550e8400-e29b-41d4-a716-4466554400f5"

    summary = json.dumps({"kpis": {"completed_interviews": 1, "avg_score": 8.5}, "notes": "OK"})
    cand = json.dumps({"c1": {"name": "A", "score": 85, "recommendation": "Favorable"}})
    rank = json.dumps([{"candidate_id": "c1", "name": "A", "score": 85}])

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-new-1"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True
    assert out.get("action") == "created"
    assert out.get("evaluation_id") == "eval-new-1"


def test_save_interview_evaluation_runtime_dict_args_rebuilds_summary(monkeypatch):
    """1619–1696: `summary`/`candidates`/`ranking` como dict o list (no solo JSON string)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f6"
    cid = "550e8400-e29b-41d4-a716-4466554400f7"

    summary_obj = {"notes": "solo notas", "extra": 1}
    cand_obj = {"c1": {"name": "A", "score": 80, "recommendation": "OK"}}
    rank_list = [{"candidate_id": "c1", "name": "A", "score": 80}]

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-dict-args"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(jid, summary_obj, cand_obj, rank_list)  # type: ignore[arg-type]
    )
    assert out["success"] is True
    assert out.get("evaluation_id") == "eval-dict-args"


def test_save_interview_evaluation_json_loads_raises_generic_parse_error(monkeypatch):
    """1645–1650: `json.loads` lanza algo distinto de `JSONDecodeError`."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-4466554400f8"
    cid = "550e8400-e29b-41d4-a716-4466554400f9"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    _real_loads = json.loads
    calls = {"n": 0}

    def _loads(s):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom-parse")
        return _real_loads(s)

    monkeypatch.setattr(supabase_tools.json, "loads", _loads)
    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            "{}",
            '{"c": 1}',
            "[]",
        )
    )
    assert out["success"] is False
    assert "boom-parse" in out.get("error", "") or "procesando" in out.get("error", "").lower()


def test_save_interview_evaluation_candidates_json_array_count(monkeypatch):
    """1656–1657: `candidates` como JSON array → cuenta por `len` de lista."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440100"
    cid = "550e8400-e29b-41d4-a716-446655440101"

    summary = json.dumps({"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"})
    cand = json.dumps([{"name": "solo lista"}])
    rank = "[]"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-list"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True


def test_save_interview_evaluation_ranking_fortalezas_and_nivel_from_score(monkeypatch):
    """1747–1763: fortalezas como string; `nivel_matcheo` vacío derivado del score."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440102"
    cid = "550e8400-e29b-41d4-a716-446655440103"

    summary = json.dumps({"kpis": {"completed_interviews": 1, "avg_score": 7}, "notes": "n"})
    cand = json.dumps({"c1": {"name": "A", "score": 72, "recommendation": "OK"}})
    rank = json.dumps(
        [
            {
                "candidate_id": "c1",
                "name": "A",
                "score": 72,
                "fortalezas_clave": "uno, dos",
                "nivel_matcheo": "",
            }
        ]
    )

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-rank"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True


def test_save_interview_evaluation_parse_else_branches_and_scalar_candidates(monkeypatch):
    """1622, 1629, 1636, 1659: tipos raros en parse y `candidates` escalar tras `json.loads`."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440104"
    cid = "550e8400-e29b-41d4-a716-446655440105"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-else"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            None,  # type: ignore[arg-type]
            3.14159,  # type: ignore[arg-type]
            {},
        )
    )
    assert out["success"] is True


def test_save_interview_evaluation_candidates_json_number_count_zero(monkeypatch):
    """1659: `json.loads` de `candidates` devuelve escalar (no dict ni lista)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440114"
    cid = "550e8400-e29b-41d4-a716-446655440115"

    summary = json.dumps({"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"})

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-num"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, "5", "[]"))
    assert out["success"] is True


def test_save_interview_evaluation_summary_without_kpis_and_empty_candidates(monkeypatch):
    """1697–1705: `summary` dict sin `kpis` y `candidates` vacío."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440106"
    cid = "550e8400-e29b-41d4-a716-446655440107"

    summary = json.dumps({"solo": "clave"})
    cand = json.dumps({})
    rank = "[]"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-min"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True


def test_save_interview_evaluation_summary_not_dict_rebuilds(monkeypatch):
    """1706–1715: `summary` no dict tras parse."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440108"
    cid = "550e8400-e29b-41d4-a716-446655440109"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-nd"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            [1, 2, 3],  # type: ignore[arg-type]
            "{}",
            "[]",
        )
    )
    assert out["success"] is True


def test_save_interview_evaluation_summary_json_list_uses_candidates_count(monkeypatch):
    """1708–1709: `summary` JSON array → `summary_dict` lista; cuenta vía `candidates_count`."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440116"
    cid = "550e8400-e29b-41d4-a716-446655440117"

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-cc"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            "[1, 2, 3]",
            "99",
            "[]",
            candidates_count=4,
        )
    )
    assert out["success"] is True


def test_save_interview_evaluation_fortalezas_scalar_normalized(monkeypatch):
    """1751–1752: `fortalezas_clave` no str ni lista."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440110"
    cid = "550e8400-e29b-41d4-a716-446655440111"

    summary = json.dumps({"kpis": {"completed_interviews": 1, "avg_score": 7}, "notes": "n"})
    cand = json.dumps({"c1": {"name": "A", "score": 70, "recommendation": "OK"}})
    rank = json.dumps(
        [
            {
                "candidate_id": "c1",
                "name": "A",
                "score": 70,
                "fortalezas_clave": 42,
                "nivel_matcheo": "",
            }
        ]
    )

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-fort"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True


def test_save_interview_evaluation_ranking_score_tiers_excelente_to_debil(monkeypatch):
    """1755–1763: nivel derivado del score cuando `nivel_matcheo` vacío."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440112"
    cid = "550e8400-e29b-41d4-a716-446655440113"

    summary = json.dumps({"kpis": {"completed_interviews": 4, "avg_score": 7}, "notes": "n"})
    cand = json.dumps(
        {
            "a": {"name": "A", "score": 85, "recommendation": "OK"},
            "b": {"name": "B", "score": 70, "recommendation": "OK"},
            "c": {"name": "C", "score": 60, "recommendation": "OK"},
            "d": {"name": "D", "score": 50, "recommendation": "OK"},
        }
    )
    rank = json.dumps(
        [
            {"candidate_id": "a", "name": "A", "score": 85, "nivel_matcheo": ""},
            {"candidate_id": "b", "name": "B", "score": 72, "nivel_matcheo": ""},
            {"candidate_id": "c", "name": "C", "score": 62, "nivel_matcheo": ""},
            {"candidate_id": "d", "name": "D", "score": 50, "nivel_matcheo": ""},
        ]
    )

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExec:
        def execute(self):
            return type("R", (), {"data": [{"id": "eval-tier"}]})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExec()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True


def test_save_interview_evaluation_update_existing_row(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440120"
    cid = "550e8400-e29b-41d4-a716-446655440121"
    ev_existing = "550e8400-e29b-41d4-a716-446655440122"

    summary = json.dumps({"kpis": {"completed_interviews": 2, "avg_score": 7.0}, "notes": "Actualizado"})
    cand = json.dumps({"c1": {"name": "B", "score": 70, "recommendation": "Condicional"}})
    rank = json.dumps([{"candidate_id": "c1", "name": "B", "score": 70}])

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "client_id": cid,
                            "interview_name": "Int",
                        }
                    ]
                },
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": [{"id": ev_existing}]})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _UpdExec:
        def execute(self):
            return type("R", (), {"data": [{"id": ev_existing}]})()

    class _UpdEq:
        def eq(self, *_a, **_k):
            return _UpdExec()

    class _UpdTbl:
        def update(self, _payload):
            return _UpdEq()

    class _Sb:
        def __init__(self):
            self._iev = 0

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                self._iev += 1
                if self._iev == 1:
                    return _IevSelectTbl()
                return _UpdTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, cand, rank))
    assert out["success"] is True
    assert out.get("action") == "updated"
    assert out.get("evaluation_id") == ev_existing


def test_save_interview_evaluation_update_without_return_rows_fails(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440130"
    cid = "550e8400-e29b-41d4-a716-446655440131"
    ev_existing = "550e8400-e29b-41d4-a716-446655440132"

    summary = json.dumps({"kpis": {"completed_interviews": 1, "avg_score": 5.0}, "notes": "x"})

    class _JdLim:
        def execute(self):
            return type(
                "R",
                (),
                {"data": [{"id": jid, "client_id": cid, "interview_name": "I"}]},
            )()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": [{"id": ev_existing}]})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _UpdExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _UpdEq:
        def eq(self, *_a, **_k):
            return _UpdExecEmpty()

    class _UpdTbl:
        def update(self, _payload):
            return _UpdEq()

    class _Sb:
        def __init__(self):
            self._iev = 0

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                self._iev += 1
                if self._iev == 1:
                    return _IevSelectTbl()
                return _UpdTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, "{}", "[]"))
    assert out["success"] is False
    assert "no retornó datos" in out.get("error", "").lower()


def test_save_interview_evaluation_jd_query_raises(monkeypatch):
    """Excepción al consultar jd_interviews (1608–1610)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440140"

    class _Lim:
        def execute(self):
            raise RuntimeError("jd select fail")

    class _Eq:
        def limit(self, _n):
            return _Lim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            jid,
            '{"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"}',
            "{}",
            "[]",
        )
    )
    assert out["success"] is False
    assert "jd_interviews" in out.get("error", "").lower() or "select fail" in out.get("error", "").lower()


def test_save_interview_evaluation_insert_returns_no_rows(monkeypatch):
    """Insert en interview_evaluations sin filas devueltas (1837–1841)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440141"
    cid = "550e8400-e29b-41d4-a716-446655440142"

    summary = json.dumps({"kpis": {"completed_interviews": 1, "avg_score": 5.0}, "notes": "x"})

    class _JdLim:
        def execute(self):
            return type("R", (), {"data": [{"id": jid, "client_id": cid, "interview_name": "I"}]})()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevSelExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevSelLimit:
        def limit(self, _n):
            return _IevSelExec()

    class _IevSelOrder:
        def order(self, *_a, **_k):
            return _IevSelLimit()

    class _IevSelEq:
        def eq(self, *_a, **_k):
            return _IevSelOrder()

    class _IevSelectTbl:
        def select(self, _cols):
            return _IevSelEq()

    class _IevInsExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _IevInsertTbl:
        def insert(self, _payload):
            return _IevInsExecEmpty()

    class _Sb:
        def __init__(self):
            self._ie_first = True

        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                if self._ie_first:
                    self._ie_first = False
                    return _IevSelectTbl()
                return _IevInsertTbl()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, "{}", "[]"))
    assert out["success"] is False
    assert "no retornó datos" in out.get("error", "").lower()


def test_save_meeting_minute_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    mid = "550e8400-e29b-41d4-a716-446655440500"
    cid = "550e8400-e29b-41d4-a716-446655440501"
    jd = "550e8400-e29b-41d4-a716-446655440502"

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "mm-ok-1"}]})()

    class _MmTable:
        def insert(self, _p):
            return _Ins()

    class _Sb:
        def table(self, name):
            assert name == "meeting_minutes_knowledge"
            return _MmTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text: [0.0, 1.0])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: None)

    out = json.loads(
        supabase_tools.save_meeting_minute(
            mid,
            cid,
            jd_interview_id=jd,
            title="Título",
            raw_minutes="Texto de minuta para embedding.",
            summary="Resumen corto",
            tags=["a", "b"],
        )
    )
    assert out["success"] is True
    assert out.get("minute_id") == "mm-ok-1"


def test_save_meeting_minute_tags_json_and_csv_and_scalar_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    mid = "550e8400-e29b-41d4-a716-446655440510"
    cid = "550e8400-e29b-41d4-a716-446655440511"

    captured_tags = []

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "mm-2"}]})()

    class _MmTable:
        def insert(self, payload):
            captured_tags.append(payload.get("tags"))
            return _Ins()

    class _Sb:
        def table(self, name):
            return _MmTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text: [0.1])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: None)

    out1 = json.loads(
        supabase_tools.save_meeting_minute(
            mid,
            cid,
            raw_minutes="x",
            tags='["x", "y"]',
        )
    )
    assert out1["success"] is True
    assert captured_tags[-1] == ["x", "y"]

    out2 = json.loads(
        supabase_tools.save_meeting_minute(
            mid,
            cid,
            raw_minutes="x",
            tags="uno, dos",
        )
    )
    assert out2["success"] is True
    assert captured_tags[-1] == ["uno", "dos"]

    out3 = json.loads(
        supabase_tools.save_meeting_minute(
            mid,
            cid,
            raw_minutes="x",
            tags="42",
        )
    )
    assert out3["success"] is True
    assert captured_tags[-1] == ["42"]


def test_save_meeting_minute_errors_no_env_raw_empty_embedding(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    out = json.loads(
        supabase_tools.save_meeting_minute(
            "550e8400-e29b-41d4-a716-446655440520",
            "550e8400-e29b-41d4-a716-446655440521",
            raw_minutes="ok",
        )
    )
    assert out["success"] is False
    assert "SUPABASE" in out.get("error", "").upper()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    out2 = json.loads(
        supabase_tools.save_meeting_minute(
            "not-uuid",
            "550e8400-e29b-41d4-a716-446655440521",
            raw_minutes="ok",
        )
    )
    assert out2["success"] is False

    out3 = json.loads(
        supabase_tools.save_meeting_minute(
            "550e8400-e29b-41d4-a716-446655440520",
            "550e8400-e29b-41d4-a716-446655440521",
            raw_minutes="   ",
        )
    )
    assert out3["success"] is False
    assert "raw_minutes" in out3.get("error", "").lower()

    class _Sb:
        def table(self, name):
            return _MmTable()

    class _MmTable:
        def insert(self, _p):
            return _Ins()

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "z"}]})()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(
        vector_tools,
        "generate_embedding",
        lambda text: (_ for _ in ()).throw(RuntimeError("no embed")),
    )
    out4 = json.loads(
        supabase_tools.save_meeting_minute(
            "550e8400-e29b-41d4-a716-446655440520",
            "550e8400-e29b-41d4-a716-446655440521",
            raw_minutes="body",
        )
    )
    assert out4["success"] is False
    assert "embedding" in out4.get("error", "").lower()


def test_save_meeting_minute_insert_empty_and_index_error_still_ok(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    mid = "550e8400-e29b-41d4-a716-446655440530"
    cid = "550e8400-e29b-41d4-a716-446655440531"

    class _InsEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MmTableEmpty:
        def insert(self, _p):
            return _InsEmpty()

    class _SbEmpty:
        def table(self, name):
            return _MmTableEmpty()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _SbEmpty())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text: [0.0])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: None)

    out_empty = json.loads(supabase_tools.save_meeting_minute(mid, cid, raw_minutes="m"))
    assert out_empty["success"] is False
    assert "vacía" in out_empty.get("error", "").lower() or "vino" in out_empty.get("error", "").lower()

    class _InsOk:
        def execute(self):
            return type("R", (), {"data": [{"id": "mm-idx"}]})()

    class _MmTableOk:
        def insert(self, _p):
            return _InsOk()

    class _SbOk:
        def table(self, name):
            return _MmTableOk()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _SbOk())
    monkeypatch.setattr(
        vector_tools,
        "update_knowledge_chunk",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("kc fail")),
    )
    out_ok = json.loads(supabase_tools.save_meeting_minute(mid, cid, raw_minutes="minuta larga " * 200))
    assert out_ok["success"] is True
    assert out_ok.get("minute_id") == "mm-idx"


def test_get_candidates_by_recruiter_empty_and_success(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    uid = "550e8400-e29b-41d4-a716-446655440600"
    clid = "550e8400-e29b-41d4-a716-446655440601"

    class _RecExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _RecEq2:
        def eq(self, *_a, **_k):
            return _RecExecEmpty()

    class _RecEq1:
        def eq(self, *_a, **_k):
            return _RecEq2()

    class _RecSelect:
        def select(self, _c):
            return _RecEq1()

    class _Sb0:
        def table(self, name):
            assert name == "candidate_recruiters"
            return _RecSelect()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb0())
    out0 = json.loads(supabase_tools.get_candidates_by_recruiter.func(uid, clid))
    assert out0 == []

    class _RecExecNull:
        def execute(self):
            return type("R", (), {"data": [{"candidate_id": None}, {}]})()

    class _RecEq2n:
        def eq(self, *_a, **_k):
            return _RecExecNull()

    class _RecEq1n:
        def eq(self, *_a, **_k):
            return _RecEq2n()

    class _RecSelectN:
        def select(self, _c):
            return _RecEq1n()

    class _SbN:
        def table(self, name):
            return _RecSelectN()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _SbN())
    outn = json.loads(supabase_tools.get_candidates_by_recruiter.func(uid, clid))
    assert outn == []

    cand_id = "550e8400-e29b-41d4-a716-446655440602"

    class _RecExecOk:
        def execute(self):
            return type("R", (), {"data": [{"candidate_id": cand_id}]})()

    class _RecEq2o:
        def eq(self, *_a, **_k):
            return _RecExecOk()

    class _RecEq1o:
        def eq(self, *_a, **_k):
            return _RecEq2o()

    class _RecSelectO:
        def select(self, _c):
            return _RecEq1o()

    class _CandExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": cand_id,
                            "name": "N",
                            "email": "e@test.example",
                            "phone": "1",
                            "cv_url": "http://c",
                            "tech_stack": ["Py"],
                            "observations": {},
                            "created_at": "t",
                        }
                    ]
                },
            )()

    class _CandIn:
        def in_(self, col, ids):
            assert col == "id"
            assert cand_id in ids
            return _CandExec()

    class _CandSelect:
        def select(self, star):
            assert star == "*"
            return _CandIn()

    class _SbOk:
        def table(self, name):
            if name == "candidate_recruiters":
                return _RecSelectO()
            if name == "candidates":
                return _CandSelect()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _SbOk())
    out_ok = json.loads(supabase_tools.get_candidates_by_recruiter.func(uid, clid, limit=5))
    assert len(out_ok) == 1
    assert out_ok[0]["id"] == cand_id
    assert out_ok[0]["name"] == "N"


def test_get_candidates_by_recruiter_execute_raises(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _RecEq2:
        def eq(self, *_a, **_k):
            raise RuntimeError("recruiter down")

    class _RecEq1:
        def eq(self, *_a, **_k):
            return _RecEq2()

    class _RecSelect:
        def select(self, _c):
            return _RecEq1()

    class _Sb:
        def table(self, name):
            return _RecSelect()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(
        supabase_tools.get_candidates_by_recruiter.func(
            "550e8400-e29b-41d4-a716-446655440610",
            "550e8400-e29b-41d4-a716-446655440611",
        )
    )
    assert "error" in out
    assert "recruiter down" in out.get("error", "").lower() or "Error obteniendo" in out.get("error", "")


def test_get_existing_meets_candidates_maps_jd_to_candidate_ids(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jd1 = "550e8400-e29b-41d4-a716-446655440200"

    class _JdExec:
        def execute(self):
            return type("R", (), {"data": [{"id": jd1}]})()

    class _JdEq:
        def eq(self, col, val):
            assert col == "status" and val == "active"
            return _JdExec()

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _MeetExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {"candidate_id": "c-one", "jd_interviews_id": jd1},
                        {"candidate_id": "c-two", "jd_interviews_id": jd1},
                    ]
                },
            )()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "jd_interviews_id" and val == jd1
            return _MeetExec()

    class _MeetTable:
        def select(self, _cols):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "meets":
                return _MeetTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_existing_meets_candidates.func())
    assert jd1 in out
    assert set(out[jd1]) == {"c-one", "c-two"}


def test_get_existing_meets_candidates_returns_error_json_on_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    def _boom(_u, _k):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(supabase_tools, "create_client", _boom)
    out = json.loads(supabase_tools.get_existing_meets_candidates.func())
    assert "error" in out
    assert "supabase down" in out.get("error", "")


def test_get_conversations_by_jd_interview_not_found(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _ExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _Eq:
        def eq(self, *_a, **_k):
            return _ExecEmpty()

    class _JdTable:
        def select(self, _star):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func("00000000-0000-0000-0000-000000000099"))
    assert "error" in out


def test_get_conversations_by_jd_interview_no_meets_returns_message(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440210"

    class _JdExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "interview_name": "Rol",
                            "client_id": None,
                            "agent_id": "ag1",
                        }
                    ]
                },
            )()

    class _JdEq:
        def eq(self, col, val):
            assert col == "id" and val == jid
            return _JdExec()

    class _JdTable:
        def select(self, _star):
            return _JdEq()

    class _MeetExec:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEq:
        def eq(self, col, val):
            return _MeetExec()

    class _MeetTable:
        def select(self, _star):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "meets":
                return _MeetTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func(jid))
    assert out.get("total_conversations") == 0
    assert "No se han presentado candidatos" in out.get("message", "")
    assert out.get("conversations") == []


def test_get_conversations_by_jd_interview_with_meets_and_conversations(monkeypatch):
    """Flujo completo: JD → cliente → meets → conversaciones con join a candidates (lista JSON)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440210"
    client_uuid = "660e8400-e29b-41d4-a716-446655440001"
    mid = "770e8400-e29b-41d4-a716-446655440002"

    jd_row = {
        "id": jid,
        "interview_name": "Entrevista QA",
        "client_id": client_uuid,
        "agent_id": "agent-99",
    }
    client_row = {
        "id": client_uuid,
        "name": "Cliente X",
        "email": "cx@example.com",
        "responsible": "Rep",
    }
    meet_rows = [{"id": mid, "jd_interviews_id": jid}]
    conv_row = {
        "meet_id": mid,
        "candidate_id": "cand-77",
        "conversation_data": {"messages": [{"role": "user", "text": "hola"}]},
        "candidates": {
            "id": "cand-77",
            "name": "Pat",
            "email": "p@p.com",
            "phone": "555",
            "cv_url": "http://cv.example/cv.pdf",
            "tech_stack": ["go", "sql"],
        },
    }
    convs_by_meet = {mid: [conv_row]}

    class _JdExec:
        def __init__(self, data):
            self._data = data

        def execute(self):
            return type("R", (), {"data": self._data})()

    class _JdEq:
        def __init__(self, row, jid_expected):
            self._row = row
            self._jid = jid_expected

        def eq(self, col, val):
            assert col == "id" and val == self._jid
            return _JdExec([self._row])

    class _JdTable:
        def __init__(self, row, jid_expected):
            self._r = row
            self._j = jid_expected

        def select(self, _star):
            return _JdEq(self._r, self._j)

    class _CliExec:
        def execute(self):
            return type("R", (), {"data": [client_row]})()

    class _CliLimit:
        def limit(self, n):
            assert n == 1
            return _CliExec()

    class _CliEq:
        def eq(self, col, val):
            assert col == "id" and val == client_uuid
            return _CliLimit()

    class _CliTable:
        def select(self, _cols):
            return _CliEq()

    class _MeetExec:
        def __init__(self, data):
            self._data = data

        def execute(self):
            return type("R", (), {"data": self._data})()

    class _MeetEq:
        def __init__(self, rows, jd_exp):
            self._rows = rows
            self._jd = jd_exp

        def eq(self, col, val):
            assert col == "jd_interviews_id" and val == self._jd
            return _MeetExec(self._rows)

    class _MeetTable:
        def __init__(self, rows, jd_exp):
            self._rows = rows
            self._jd = jd_exp

        def select(self, _star):
            return _MeetEq(self._rows, self._jd)

    class _ConvExec:
        def __init__(self, data):
            self._data = data

        def execute(self):
            return type("R", (), {"data": self._data})()

    class _ConvLimit:
        def __init__(self, rows):
            self._rows = rows

        def limit(self, n):
            return _ConvExec(self._rows[:n] if n is not None else self._rows)

    class _ConvEq:
        def __init__(self, conv_map):
            self._map = conv_map

        def eq(self, col, val):
            assert col == "meet_id"
            rows = self._map.get(val, [])
            return _ConvLimit(rows)

    class _ConvTable:
        def __init__(self, conv_map):
            self._map = conv_map

        def select(self, _star):
            return _ConvEq(self._map)

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable(jd_row, jid)
            if name == "clients":
                return _CliTable()
            if name == "meets":
                return _MeetTable(meet_rows, jid)
            if name == "conversations":
                return _ConvTable(convs_by_meet)
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func(jid, limit=50))

    assert isinstance(out, list)
    assert len(out) == 1
    item = out[0]
    assert item["meet_id"] == mid
    assert item["candidate_id"] == "cand-77"
    assert item["conversation_data"]["messages"][0]["text"] == "hola"
    assert item["candidate"]["name"] == "Pat"
    assert item["candidate"]["tech_stack"] == ["go", "sql"]
    assert item["jd_interview_id"] == jid
    assert item["jd_interview_name"] == "Entrevista QA"
    assert item["jd_interview_agent_id"] == "agent-99"
    assert item["client"]["name"] == "Cliente X"
    assert item["client"]["email"] == "cx@example.com"


def test_get_conversations_by_jd_interview_two_meets_accumulates_rows(monkeypatch):
    """Varios meets: una query de conversations por meet_id; resultado es lista plana."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440311"
    m1 = "11111111-1111-1111-1111-111111111111"
    m2 = "22222222-2222-2222-2222-222222222222"

    jd_row = {
        "id": jid,
        "interview_name": "Solo JD",
        "client_id": None,
        "agent_id": "ag",
    }
    meet_rows = [
        {"id": m1, "jd_interviews_id": jid},
        {"id": m2, "jd_interviews_id": jid},
    ]

    def _conv(mid: str, cand: str):
        return {
            "meet_id": mid,
            "candidate_id": cand,
            "conversation_data": {},
            "candidates": {
                "id": cand,
                "name": cand,
                "email": None,
                "phone": None,
                "cv_url": None,
                "tech_stack": None,
            },
        }

    convs_by_meet = {m1: [_conv(m1, "a")], m2: [_conv(m2, "b")]}

    class _Exec:
        def __init__(self, data):
            self._data = data

        def execute(self):
            return type("R", (), {"data": self._data})()

    class _JdEq:
        def eq(self, col, val):
            assert col == "id" and val == jid
            return _Exec([jd_row])

    class _MeetEq:
        def eq(self, col, val):
            assert col == "jd_interviews_id" and val == jid
            return _Exec(meet_rows)

    class _ConvEq:
        def __init__(self, conv_map):
            self._map = conv_map

        def eq(self, col, val):
            assert col == "meet_id"
            return _ConvLim(self._map.get(val, []))

    class _ConvLim:
        def __init__(self, rows):
            self._rows = rows

        def limit(self, n):
            return _Exec(self._rows)

    class _JdTable:
        def select(self, _star):
            return _JdEq()

    class _MeetTable:
        def select(self, _star):
            return _MeetEq()

    class _ConvTable:
        def __init__(self, conv_map):
            self._conv_map = conv_map

        def select(self, _star):
            return _ConvEq(self._conv_map)

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "meets":
                return _MeetTable()
            if name == "conversations":
                return _ConvTable(convs_by_meet)
            raise AssertionError(f"unexpected {name}")

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func(jid))

    assert len(out) == 2
    assert {x["candidate_id"] for x in out} == {"a", "b"}
    assert all(x["client"] is None for x in out)
    assert all(x["jd_interview_name"] == "Solo JD" for x in out)


def test_get_conversations_by_jd_interview_client_fetch_exception_logged(monkeypatch):
    """680–686: fallo al leer `clients` no tumba el flujo principal."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440210"
    client_uuid = "660e8400-e29b-41d4-a716-446655440001"
    mid = "770e8400-e29b-41d4-a716-446655440002"

    jd_row = {
        "id": jid,
        "interview_name": "Rol",
        "client_id": client_uuid,
        "agent_id": "ag1",
    }
    conv_row = {
        "meet_id": mid,
        "candidate_id": "c1",
        "conversation_data": {},
        "candidates": None,
    }

    class _JdExec:
        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _JdEq:
        def eq(self, col, val):
            assert col == "id" and val == jid
            return _JdExec()

    class _JdTable:
        def select(self, _star):
            return _JdEq()

    class _CliLimit:
        def limit(self, _n):
            raise RuntimeError("clients down")

    class _CliEq:
        def eq(self, col, val):
            return _CliLimit()

    class _CliTable:
        def select(self, _cols):
            return _CliEq()

    class _MeetExec:
        def execute(self):
            return type("R", (), {"data": [{"id": mid, "jd_interviews_id": jid}]})()

    class _MeetEq:
        def eq(self, col, val):
            return _MeetExec()

    class _MeetTable:
        def select(self, _star):
            return _MeetEq()

    class _ConvExec:
        def execute(self):
            return type("R", (), {"data": [conv_row]})()

    class _ConvLimit:
        def limit(self, _n):
            return _ConvExec()

    class _ConvEq:
        def eq(self, col, val):
            return _ConvLimit()

    class _ConvTable:
        def select(self, _star):
            return _ConvEq()

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "clients":
                return _CliTable()
            if name == "meets":
                return _MeetTable()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func(jid))
    assert isinstance(out, list)
    assert out[0].get("client") is None


def test_get_conversations_by_jd_interview_meets_data_none_raises_outer(monkeypatch):
    """744–746: `meets_response.data` no iterable."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440210"

    class _JdExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": jid,
                            "interview_name": "Rol",
                            "client_id": None,
                            "agent_id": "ag1",
                        }
                    ]
                },
            )()

    class _JdEq:
        def eq(self, col, val):
            return _JdExec()

    class _JdTable:
        def select(self, _star):
            return _JdEq()

    class _MeetExec:
        def execute(self):
            return type("R", (), {"data": None})()

    class _MeetEq:
        def eq(self, col, val):
            return _MeetExec()

    class _MeetTable:
        def select(self, _star):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "meets":
                return _MeetTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_conversations_by_jd_interview.func(jid))
    assert "error" in out


def test_get_candidates_data_respects_limit(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    rows = [
        {
            "id": "1",
            "name": "A",
            "email": "a@a",
            "phone": None,
            "cv_url": None,
            "tech_stack": [],
            "observations": None,
            "created_at": None,
        }
    ]

    class _Lim:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _CandSelect:
        def limit(self, n):
            assert n == 2
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _CandSelect()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_candidates_data.func({"limit": 2}))
    assert len(out) == 1
    assert out[0]["name"] == "A"


def test_get_all_jd_interviews_with_client_id_filter(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    cid = "550e8400-e29b-41d4-a716-446655440400"
    row = {
        "id": "jd-1",
        "interview_name": "Dev",
        "agent_id": "a1",
        "job_description": "jd",
        "tech_stack": [],
        "client_id": cid,
        "created_at": None,
    }

    class _Chain:
        def __init__(self):
            self._seen: list[tuple[str, str]] = []

        def eq(self, col, val):
            self._seen.append((col, val))
            return self

        def execute(self):
            assert ("client_id", cid) in self._seen
            assert ("status", "active") in self._seen
            return type("R", (), {"data": [row]})()

    class _JdTable:
        def select(self, _star):
            return _Chain()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_all_jd_interviews.func(cid))
    assert len(out) == 1
    assert out[0]["id"] == "jd-1"


def test_get_all_jd_interviews_without_client_id(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Chain:
        def eq(self, col, val):
            assert col == "status" and val == "active"
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _JdTable:
        def select(self, _star):
            return _Chain()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_all_jd_interviews.func())
    assert out == []


def test_get_all_jd_interviews_returns_error_json_on_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    def _boom(_u, _k):
        raise RuntimeError("jd query fail")

    monkeypatch.setattr(supabase_tools, "create_client", _boom)
    out = json.loads(supabase_tools.get_all_jd_interviews.func())
    assert "error" in out
    assert "jd query fail" in out.get("error", "")


def test_get_candidates_data_returns_error_on_execute_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _CandTable:
        def select(self, _star):
            return _BadLimit()

    class _BadLimit:
        def limit(self, _n):
            raise RuntimeError("candidates table down")

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_candidates_data.func(10))
    assert "error" in out
    assert "candidates table down" in out.get("error", "")


def test_get_candidates_data_limit_non_numeric_string_defaults_to_100(monkeypatch):
    """Rama 1362–1365: int(limit) falla → limit 100."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Lim:
        def execute(self):
            return type("R", (), {"data": []})()

    class _CandSelect:
        def limit(self, n):
            assert n == 100
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _CandSelect()

    class _Sb:
        def table(self, name):
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_candidates_data.func("not-a-number"))
    assert out == []


def test_get_candidates_data_limit_dict_unparseable_defaults_to_100(monkeypatch):
    """1354–1357: dict `limit` sin entero usable → 100."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Lim:
        def execute(self):
            return type("R", (), {"data": []})()

    class _CandSelect:
        def limit(self, n):
            assert n == 100
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _CandSelect()

    class _Sb:
        def table(self, name):
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_candidates_data.func({"default": "not-int", "value": None}))
    assert out == []


def test_get_candidates_data_limit_none_defaults_to_100(monkeypatch):
    """1358–1359: `limit is None` → 100."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    class _Lim:
        def execute(self):
            return type("R", (), {"data": []})()

    class _CandSelect:
        def limit(self, n):
            assert n == 100
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _CandSelect()

    class _Sb:
        def table(self, name):
            return _CandTable()

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    out = json.loads(supabase_tools.get_candidates_data.func(None))
    assert out == []


def test_create_candidate_observations_dict_passed_directly(monkeypatch):
    """1458–1459: `observations` ya es dict."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    obs = {"work_experience": [{"company": "ACME"}], "other": "note"}

    class _EmptySelectObs:
        def eq(self, *_a):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Ins:
        def execute(self):
            return type("R", (), {"data": [{"id": "c-obs-dict", "email": "od@test.example"}]})()

    class _CandTable:
        def select(self, *_a):
            return _EmptySelectObs()

        def insert(self, payload):
            assert payload["observations"] == obs
            return _Ins()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda _r: None)

    out = json.loads(
        supabase_tools.create_candidate.func(
            "OD",
            "od@test.example",
            "1",
            "http://cv",
            "Go",
            observations=obs,
        )
    )
    assert out["success"] is True


def test_save_interview_evaluation_db_select_raises_returns_error(monkeypatch):
    """Bloque try BD: fallo al listar interview_evaluations (1843–1850)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    jid = "550e8400-e29b-41d4-a716-446655440700"
    cid = "550e8400-e29b-41d4-a716-446655440701"

    class _JdLim:
        def execute(self):
            return type("R", (), {"data": [{"id": jid, "client_id": cid, "interview_name": "I"}]})()

    class _JdEq:
        def limit(self, _n):
            return _JdLim()

        def eq(self, *_a, **_k):
            return self

    class _JdTable:
        def select(self, _cols):
            return _JdEq()

    class _IevExec:
        def execute(self):
            raise RuntimeError("ie table down")

    class _IevLim:
        def limit(self, _n):
            return _IevExec()

    class _IevOrd:
        def order(self, *_a, **_k):
            return _IevLim()

    class _IevEq:
        def eq(self, *_a, **_k):
            return _IevOrd()

    class _IevTable:
        def select(self, _cols):
            return _IevEq()

    class _Sb:
        def table(self, name):
            if name == "jd_interviews":
                return _JdTable()
            if name == "interview_evaluations":
                return _IevTable()
            raise AssertionError(name)

    monkeypatch.setattr(supabase_tools, "create_client", lambda u, k: _Sb())
    summary = json.dumps({"kpis": {"completed_interviews": 0, "avg_score": 0}, "notes": "n"})
    out = json.loads(supabase_tools.save_interview_evaluation.func(jid, summary, "{}", "[]"))
    assert out["success"] is False
    assert "base de datos" in out.get("error", "").lower() or "ie table" in out.get("error", "").lower()


def test_save_interview_evaluation_outer_exception_from_create_client(monkeypatch):
    """1852–1859: fallo antes del flujo principal."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(
        supabase_tools,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("no client")),
    )
    out = json.loads(
        supabase_tools.save_interview_evaluation.func(
            "550e8400-e29b-41d4-a716-446655440710",
            "{}",
            "{}",
            "[]",
        )
    )
    assert out["success"] is False
    assert "interview_evaluations" in out.get("error", "").lower() or "no client" in out.get("error", "").lower()


def test_save_meeting_minute_outer_exception(monkeypatch):
    """1247–1252: excepción genérica (p. ej. create_client)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(
        supabase_tools,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("minute db")),
    )
    out = json.loads(
        supabase_tools.save_meeting_minute(
            "550e8400-e29b-41d4-a716-446655440720",
            "550e8400-e29b-41d4-a716-446655440721",
            raw_minutes="texto",
        )
    )
    assert out["success"] is False
    assert "minute db" in out.get("error", "").lower() or "guardando minuta" in out.get("error", "").lower()


def test_send_evaluation_email_success(monkeypatch):
    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    def _post(*_a, **_k):
        return _Resp()

    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("Asunto test", "Cuerpo"))
    assert out.get("status") == "success"
    assert "dest@test.example" in out.get("message", "")


def test_send_evaluation_email_request_exception_returns_error_json(monkeypatch):
    def _post(*_a, **_k):
        raise requests.exceptions.RequestException("smtp down")

    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "body"))
    assert out.get("status") == "error"
    assert "smtp down" in out.get("message", "")


def test_send_evaluation_email_connection_error_returns_error_json(monkeypatch):
    """260–263: ConnectionError se re-lanza y cae en RequestException."""
    monkeypatch.setattr(
        supabase_tools.requests,
        "post",
        lambda *_a, **_k: (_ for _ in ()).throw(requests.exceptions.ConnectionError("refused")),
    )
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "body"))
    assert out.get("status") == "error"
    assert "refused" in out.get("message", "")


def test_send_evaluation_email_timeout_returns_error_json(monkeypatch):
    """264–267: Timeout se re-lanza y cae en RequestException."""
    monkeypatch.setattr(
        supabase_tools.requests,
        "post",
        lambda *_a, **_k: (_ for _ in ()).throw(requests.exceptions.Timeout("slow")),
    )
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "body"))
    assert out.get("status") == "error"
    assert "slow" in out.get("message", "")


def test_send_evaluation_email_http_error_returns_error_json(monkeypatch):
    """268–273: HTTPError tras raise_for_status."""

    class _Resp:
        status_code = 502
        text = "bad gateway"

        def raise_for_status(self):
            err = requests.exceptions.HTTPError("502")
            err.response = self
            raise err

    monkeypatch.setattr(supabase_tools.requests, "post", lambda *_a, **_k: _Resp())
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "body"))
    assert out.get("status") == "error"
    assert "502" in out.get("message", "")


def test_send_evaluation_email_uses_email_from_body_when_report_to_empty(monkeypatch):
    """207–214: primer email en el cuerpo si REPORT_TO_EMAIL está vacío."""

    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    captured = {}

    def _post(_url, json=None, **_k):
        captured["to"] = json.get("to_email")
        return _Resp()

    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.delenv("REPORT_TO_EMAIL", raising=False)
    body = "Reporte para cliente@empresa.com — gracias."
    out = json.loads(supabase_tools.send_evaluation_email.func("Asunto", body))
    assert out.get("status") == "success"
    assert captured.get("to") == "cliente@empresa.com"
    assert "cliente@empresa.com" in out.get("message", "")


def test_send_evaluation_email_log_task_start_raises_returns_error_json(monkeypatch):
    """301–309: excepción genérica si log_task_start falla antes del POST."""
    monkeypatch.setattr(
        supabase_tools.evaluation_logger,
        "log_task_start",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("log start")),
    )
    monkeypatch.setenv("REPORT_TO_EMAIL", "dest@test.example")
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "body"))
    assert out.get("status") == "error"
    assert "log start" in out.get("message", "")


def test_send_evaluation_email_first_regex_raises_then_fallback_email(monkeypatch):
    """209–216 y 218–234: `re.search` lanza en el primer try; destino final fallback."""
    calls = {"n": 0}

    def _search(_pat, _s, _flags=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("regex boom")
        return None

    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    captured = {}

    def _post(_url, json=None, **_k):
        captured["to"] = json.get("to_email")
        return _Resp()

    monkeypatch.setattr(re, "search", _search)
    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.delenv("REPORT_TO_EMAIL", raising=False)
    out = json.loads(supabase_tools.send_evaluation_email.func("Subj", "sin email en cuerpo"))
    assert out.get("status") == "success"
    assert captured.get("to") == "flocklab.id@gmail.com"


def test_send_evaluation_email_second_regex_raises_fallback_email(monkeypatch):
    """221–233: segundo `try/except` con `re.search` que lanza → fallback."""
    calls = {"n": 0}

    def _search(_pat, _s, _flags=0):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        raise RuntimeError("second block")

    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    captured = {}

    def _post(_url, json=None, **_k):
        captured["to"] = json.get("to_email")
        return _Resp()

    monkeypatch.setattr(re, "search", _search)
    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.delenv("REPORT_TO_EMAIL", raising=False)
    out = json.loads(supabase_tools.send_evaluation_email.func("S", "cuerpo"))
    assert out.get("status") == "success"
    assert captured.get("to") == "flocklab.id@gmail.com"


def test_send_evaluation_email_second_block_sets_email_when_first_try_raises(monkeypatch):
    """209–216 + 226–228: el primer `re.search` lanza; el segundo encuentra email en el cuerpo."""
    calls = {"n": 0}
    _real_search = re.search

    def _search(pat, s, flags=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("primer bloque")
        return _real_search(pat, s, flags)

    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    captured = {}

    def _post(_url, json=None, **_k):
        captured["to"] = json.get("to_email")
        return _Resp()

    monkeypatch.setattr(re, "search", _search)
    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    monkeypatch.delenv("REPORT_TO_EMAIL", raising=False)
    body = "Contacto: soporte@cliente.example"
    out = json.loads(supabase_tools.send_evaluation_email.func("Subj", body))
    assert out.get("status") == "success"
    assert captured.get("to") == "soporte@cliente.example"


def test_send_match_notification_email_success(monkeypatch):
    class _Resp:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(supabase_tools.requests, "post", lambda *_a, **_k: _Resp())
    out = json.loads(supabase_tools.send_match_notification_email.func("match@test.example", "Match", "body"))
    assert out.get("status") == "success"
    assert "match@test.example" in out.get("message", "")


def test_send_match_notification_email_request_exception(monkeypatch):
    def _post(*_a, **_k):
        raise requests.exceptions.RequestException("conn refused")

    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    out = json.loads(supabase_tools.send_match_notification_email.func("a@b.com", "S", "b"))
    assert out.get("status") == "error"
    assert "conn refused" in out.get("message", "")


def test_send_match_notification_email_unexpected_exception(monkeypatch):
    def _post(*_a, **_k):
        raise ValueError("boom")

    monkeypatch.setattr(supabase_tools.requests, "post", _post)
    out = json.loads(supabase_tools.send_match_notification_email.func("a@b.com", "S", "b"))
    assert out.get("status") == "error"
    assert "boom" in out.get("message", "")
