"""Éxito en rutas ElevenLabs con Supabase y APIs externas mockeados."""

import json

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app  # noqa: E402


def _patch_run_pool(monkeypatch):
    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)


def _fake_client_email_tool():
    class _T:
        @staticmethod
        def func(client_id):
            return json.dumps({"email": "client@test.example", "name": "Test Client", "client_id": client_id})

    return _T()


def test_create_elevenlabs_agent_success(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440000"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista QA",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _UpdateChain:
        def __init__(self, upd):
            self._upd = upd

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            merged = {**jd_row, **self._upd}
            return type("R", (), {"data": [merged]})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

        def update(self, data):
            return _UpdateChain(data)

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **kwargs: {"agent_id": "elb-agent-1", "name": "Agente Generado"},
    )

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    r = client.post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["agent_id"] == "elb-agent-1"
    assert data["jd_interview_id"] == jd_id


def test_create_elevenlabs_agent_success_when_result_is_object_with_agent_id(monkeypatch):
    """Rama `hasattr(elevenlabs_result, 'agent_id')` (1342–1343)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440010"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista Obj",
        "client_id": "550e8400-e29b-41d4-a716-446655440011",
    }

    class _UpdateChain:
        def __init__(self, upd):
            self._upd = upd

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            merged = {**jd_row, **self._upd}
            return type("R", (), {"data": [merged]})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

        def update(self, data):
            return _UpdateChain(data)

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    class _ElbObj:
        agent_id = "obj-agent-99"
        name = "Nombre Obj"

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(api_module, "create_elevenlabs_agent", lambda **kwargs: _ElbObj())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    r = client.post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["agent_id"] == "obj-agent-99"
    # Con resultado tipo objeto solo se lee `agent_id`; el nombre final sigue siendo el temporal (interview_name).
    assert data["agent_name"] == "Entrevista Obj"


def test_create_elevenlabs_agent_success_when_index_jd_interview_raises(monkeypatch):
    """1377–1379: fallo de indexación se registra y no tumba el 200."""
    jd_id = "550e8400-e29b-41d4-a716-446655440020"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista IndexErr",
        "client_id": "550e8400-e29b-41d4-a716-446655440021",
    }

    class _UpdateChain:
        def __init__(self, upd):
            self._upd = upd

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            merged = {**jd_row, **self._upd}
            return type("R", (), {"data": [merged]})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

        def update(self, data):
            return _UpdateChain(data)

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **kwargs: {"agent_id": "elb-after-index-fail", "name": "OK"},
    )

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(
        vector_tools, "index_jd_interview", lambda _row: (_ for _ in ()).throw(RuntimeError("kb index"))
    )

    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    r = client.post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["agent_id"] == "elb-after-index-fail"


def test_update_elevenlabs_agent_success(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440002"
    jd_row = {
        "id": jd_id,
        "job_description": "JD para prompt " * 5,
        "interview_name": "Dev Senior",
        "client_id": "550e8400-e29b-41d4-a716-446655440003",
        "agent_id": "existing-agent-9",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **kwargs: {"prompt": "Prompt sintético de test"},
    )
    monkeypatch.setattr(api_module, "update_elevenlabs_agent_prompt", lambda agent_id, prompt_text: {"ok": True})

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    r = client.patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["agent_id"] == "existing-agent-9"
    assert data["jd_interview_id"] == jd_id


def test_update_elevenlabs_agent_returns_404_when_jd_not_found(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440099"

    class _JdTable:
        def select(self, *_cols):
            return _SelectEmpty()

    class _SelectEmpty:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    r = client.patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 404
    assert "jd_interview" in r.json().get("detail", "").lower()


def test_create_elevenlabs_agent_returns_500_when_elevenlabs_returns_none(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440030"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista QA",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreate(jd_row)

    class _SelectChainCreate:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(api_module, "create_elevenlabs_agent", lambda **kwargs: None)
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "ElevenLabs" in r.json().get("detail", "")


def test_create_elevenlabs_agent_returns_500_when_agent_id_missing(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440031"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista QA",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreate(jd_row)

    class _SelectChainCreate:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(api_module, "create_elevenlabs_agent", lambda **kwargs: {"name": "solo nombre"})
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "agent_id" in r.json().get("detail", "").lower()


def test_create_elevenlabs_agent_returns_500_when_update_returns_no_rows(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440032"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Entrevista QA",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _UpdateNoRows:
        def eq(self, *_a, **_k):
            return _ExecEmpty()

    class _ExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreate(jd_row)

        def update(self, _data):
            return _UpdateNoRows()

    class _SelectChainCreate:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **kwargs: {"agent_id": "elb-agent-1", "name": "Agente Generado"},
    )

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "actualizar" in r.json().get("detail", "").lower() or "jd_interview" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_500_on_unexpected_exception(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440040"
    jd_row = {
        "id": jd_id,
        "job_description": "JD para prompt " * 5,
        "interview_name": "Dev Senior",
        "client_id": "550e8400-e29b-41d4-a716-446655440003",
        "agent_id": "existing-agent-9",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainUp()

    class _SelectChainUp:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("prompt boom")),
    )
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "prompt boom" in r.json().get("detail", "") or "Error al actualizar" in r.json().get("detail", "")


def test_create_elevenlabs_agent_returns_404_when_jd_not_found(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440088"

    class _JdTable:
        def select(self, *_cols):
            return _SelectEmpty()

    class _SelectEmpty:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 404


def test_create_elevenlabs_agent_returns_400_when_job_description_empty(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440077"
    jd_row = {
        "id": jd_id,
        "job_description": "",
        "interview_name": "X",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainJd(jd_row)

    class _SelectChainJd:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400


def test_create_elevenlabs_agent_returns_400_when_client_id_missing(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440066"
    jd_row = {
        "id": jd_id,
        "job_description": "Texto suficiente " * 5,
        "interview_name": "Y",
        "client_id": None,
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainJd(jd_row)

    class _SelectChainJd:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400


def test_create_elevenlabs_agent_returns_400_when_get_client_email_error(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440055"
    jd_row = {
        "id": jd_id,
        "job_description": "Texto suficiente " * 5,
        "interview_name": "Z",
        "client_id": "550e8400-e29b-41d4-a716-446655440001",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainJd(jd_row)

    class _SelectChainJd:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            return _JdTable()

    class _ErrEmail:
        @staticmethod
        def func(client_id):
            return json.dumps({"error": "cliente no encontrado"})

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _ErrEmail())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400


def test_update_elevenlabs_agent_returns_400_when_job_description_empty(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440200"
    jd_row = {
        "id": jd_id,
        "job_description": "",
        "interview_name": "Patch JD vacío",
        "client_id": "550e8400-e29b-41d4-a716-446655440201",
        "agent_id": "agent-patch-1",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "job_description" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_400_when_no_agent_id(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440202"
    jd_row = {
        "id": jd_id,
        "job_description": "Texto JD " * 4,
        "interview_name": "Sin agent",
        "client_id": "550e8400-e29b-41d4-a716-446655440203",
        "agent_id": None,
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "agent_id" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_400_when_no_client_id(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440204"
    jd_row = {
        "id": jd_id,
        "job_description": "Texto JD " * 4,
        "interview_name": "Sin client",
        "client_id": None,
        "agent_id": "agent-patch-2",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "client_id" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_success_when_index_jd_interview_raises(monkeypatch):
    """1190–1191: error de re-indexación no tumba el 200 en PATCH."""
    jd_id = "550e8400-e29b-41d4-a716-446655440205"
    jd_row = {
        "id": jd_id,
        "job_description": "JD para prompt " * 5,
        "interview_name": "Index fail patch",
        "client_id": "550e8400-e29b-41d4-a716-446655440206",
        "agent_id": "existing-agent-patch-idx",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **kwargs: {"prompt": "Prompt patch index err"},
    )
    monkeypatch.setattr(api_module, "update_elevenlabs_agent_prompt", lambda agent_id, prompt_text: {"ok": True})

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(
        vector_tools,
        "index_jd_interview",
        lambda _row: (_ for _ in ()).throw(RuntimeError("reindex fail")),
    )

    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json().get("status") == "success"


def test_create_elevenlabs_agent_returns_500_when_get_client_email_unresolvable(monkeypatch):
    """1277–1279: Tool `get_client_email` sin __wrapped__/func/_func."""
    jd_id = "550e8400-e29b-41d4-a716-446655440300"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Sin email tool",
        "client_id": "550e8400-e29b-41d4-a716-446655440301",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", object())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "get_client_email" in r.json().get("detail", "").lower()


def test_create_elevenlabs_agent_success_when_result_is_object_with_id_only(monkeypatch):
    """Rama `hasattr(elevenlabs_result, 'id')` sin `agent_id` (1344–1345)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440310"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Obj solo id",
        "client_id": "550e8400-e29b-41d4-a716-446655440311",
    }

    class _UpdateChain:
        def __init__(self, upd):
            self._upd = upd

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            merged = {**jd_row, **self._upd}
            return type("R", (), {"data": [merged]})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

        def update(self, data):
            return _UpdateChain(data)

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    class _ElbObj:
        id = "obj-by-id-only"

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(api_module, "create_elevenlabs_agent", lambda **kwargs: _ElbObj())

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json()["agent_id"] == "obj-by-id-only"


def test_update_elevenlabs_agent_returns_500_when_get_client_email_unresolvable(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440320"
    jd_row = {
        "id": jd_id,
        "job_description": "JD para prompt " * 5,
        "interview_name": "Patch sin tool",
        "client_id": "550e8400-e29b-41d4-a716-446655440321",
        "agent_id": "agent-320",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

    class _SelectChain:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", object())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "get_client_email" in r.json().get("detail", "").lower()


def _jd_row_patch_base(jd_id: str, agent_id: str = "existing-agent-9"):
    return {
        "id": jd_id,
        "job_description": "JD para prompt " * 5,
        "interview_name": "Dev Senior",
        "client_id": "550e8400-e29b-41d4-a716-446655440003",
        "agent_id": agent_id,
    }


def _patch_supabase_jd_only(jd_row: dict):
    class _JdTable:
        def select(self, *_cols):
            return _SelectChainPatch()

    class _SelectChainPatch:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    return _Sb


def test_update_elevenlabs_agent_success_get_client_email_wrapped(monkeypatch):
    """PATCH: `get_client_email.__wrapped__` (1106–1107)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440400"
    jd_row = _jd_row_patch_base(jd_id)

    def _wrapped_email(*args, **kwargs):
        client_id = args[-1]
        return json.dumps({"email": "wrapped@test.example", "name": "W", "client_id": client_id})

    class _EmailTool:
        __wrapped__ = _wrapped_email

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _EmailTool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **kwargs: {"prompt": "Prompt vía __wrapped__"},
    )
    monkeypatch.setattr(api_module, "update_elevenlabs_agent_prompt", lambda agent_id, prompt_text: {"ok": True})

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json().get("status") == "success"


def test_update_elevenlabs_agent_success_get_client_email_dunder_func(monkeypatch):
    """PATCH: `get_client_email._func` (1110–1111)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440401"
    jd_row = _jd_row_patch_base(jd_id)

    def _func_email(*args, **kwargs):
        client_id = args[-1]
        return json.dumps({"email": "usfunc@test.example", "name": "U", "client_id": client_id})

    class _EmailTool:
        _func = _func_email

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _EmailTool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **kwargs: {"prompt": "Prompt vía _func"},
    )
    monkeypatch.setattr(api_module, "update_elevenlabs_agent_prompt", lambda agent_id, prompt_text: {"ok": True})

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json().get("status") == "success"


def test_update_elevenlabs_agent_returns_400_when_get_client_email_payload_has_error(monkeypatch):
    """1120–1123: JSON con clave `error`."""
    jd_id = "550e8400-e29b-41d4-a716-446655440402"
    jd_row = _jd_row_patch_base(jd_id)

    class _ErrEmail:
        @staticmethod
        def func(client_id):
            return json.dumps({"error": "cliente inexistente"})

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _ErrEmail())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "error" in r.json().get("detail", "").lower() or "cliente" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_400_when_sender_email_empty(monkeypatch):
    """1125–1129."""
    jd_id = "550e8400-e29b-41d4-a716-446655440403"
    jd_row = _jd_row_patch_base(jd_id)

    class _EmptyEmail:
        @staticmethod
        def func(client_id):
            return json.dumps({"email": "", "name": "Sin email"})

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _EmptyEmail())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "email" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_500_when_generated_prompt_empty(monkeypatch):
    """1137–1140."""
    jd_id = "550e8400-e29b-41d4-a716-446655440404"
    jd_row = _jd_row_patch_base(jd_id)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(api_module, "generate_elevenlabs_prompt_from_jd", lambda **kwargs: {"prompt": "   "})
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "prompt" in r.json().get("detail", "").lower()


def test_update_elevenlabs_agent_returns_500_when_update_agent_prompt_falsy(monkeypatch):
    """1174–1178: `update_elevenlabs_agent_prompt` devuelve valor falso."""
    jd_id = "550e8400-e29b-41d4-a716-446655440405"
    jd_row = _jd_row_patch_base(jd_id)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _patch_supabase_jd_only(jd_row)())
    monkeypatch.setattr(api_module, "get_client_email", _fake_client_email_tool())
    monkeypatch.setattr(
        api_module,
        "generate_elevenlabs_prompt_from_jd",
        lambda **kwargs: {"prompt": "OK"},
    )
    monkeypatch.setattr(api_module, "update_elevenlabs_agent_prompt", lambda agent_id, prompt_text: None)
    _patch_run_pool(monkeypatch)

    r = TestClient(app).patch("/update-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "elevenlabs" in r.json().get("detail", "").lower() or "actualizar" in r.json().get("detail", "").lower()


def test_create_elevenlabs_agent_success_get_client_email_wrapped(monkeypatch):
    """POST create: `get_client_email.__wrapped__` (1270–1271)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440410"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Wrapped POST",
        "client_id": "550e8400-e29b-41d4-a716-446655440411",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreatePost(jd_row)

        def update(self, data):
            return _UpdateChainPost(jd_row, data)

    class _SelectChainCreatePost:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _UpdateChainPost:
        def __init__(self, row, upd):
            self._row = {**row, **upd}

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    def _wrapped_email(*args, **kwargs):
        client_id = args[-1]
        return json.dumps({"email": "cpost@test.example", "name": "C", "client_id": client_id})

    class _EmailTool:
        __wrapped__ = _wrapped_email

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _EmailTool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **kwargs: {"agent_id": "agent-wrapped-post", "name": "N"},
    )

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json().get("agent_id") == "agent-wrapped-post"


def test_create_elevenlabs_agent_success_get_client_email_dunder_func(monkeypatch):
    """POST create: `get_client_email._func` (1274–1275)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440420"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Usfunc POST",
        "client_id": "550e8400-e29b-41d4-a716-446655440421",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreatePost(jd_row)

        def update(self, data):
            return _UpdateChainPost(jd_row, data)

    class _SelectChainCreatePost:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _UpdateChainPost:
        def __init__(self, row, upd):
            self._row = {**row, **upd}

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    def _func_email(*args, **kwargs):
        client_id = args[-1]
        return json.dumps({"email": "uspost@test.example", "name": "U", "client_id": client_id})

    class _EmailTool:
        _func = _func_email

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _EmailTool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **kwargs: {"agent_id": "agent-usfunc-post", "name": "N2"},
    )

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)

    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 200
    assert r.json().get("agent_id") == "agent-usfunc-post"


def test_create_elevenlabs_agent_returns_400_when_sender_email_empty(monkeypatch):
    """1291–1295: email vacío tras get_client_email."""
    jd_id = "550e8400-e29b-41d4-a716-446655440430"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción larga " * 10,
        "interview_name": "Sin sender",
        "client_id": "550e8400-e29b-41d4-a716-446655440431",
    }

    class _JdTable:
        def select(self, *_cols):
            return _SelectChainCreatePost(jd_row)

    class _SelectChainCreatePost:
        def __init__(self, row):
            self._row = row

        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [self._row]})()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    class _EmptyEmail:
        @staticmethod
        def func(client_id):
            return json.dumps({"email": "", "name": "X"})

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    monkeypatch.setattr(api_module, "get_client_email", _EmptyEmail())
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 400
    assert "email" in r.json().get("detail", "").lower()


def test_create_elevenlabs_agent_returns_500_on_unexpected_exception(monkeypatch):
    """1395–1401: excepción genérica (p. ej. create_client falla)."""
    jd_id = "550e8400-e29b-41d4-a716-446655440440"

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(
        api_module,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("supabase caído")),
    )
    _patch_run_pool(monkeypatch)

    r = TestClient(app).post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})
    assert r.status_code == 500
    assert "supabase" in r.json().get("detail", "").lower() or "elevenlabs" in r.json().get("detail", "").lower()
