"""POST /chatbot camino feliz con Supabase, búsqueda vectorial y OpenAI mockeados."""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app  # noqa: E402


def test_chatbot_returns_answer_with_mocked_openai_and_rag(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _CountExec:
        count = 4

    class _KcLimit:
        def execute(self):
            return _CountExec()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(
        api_module,
        "search_similar_chunks",
        lambda **kwargs: [
            {
                "content": "Candidata Ana domina Python y FastAPI.",
                "entity_type": "candidate",
                "entity_id": "c1",
                "metadata": {"name": "Ana"},
            }
        ],
    )

    class _Msg:
        content = "Respuesta sintética del test."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, **_kwargs):
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "¿Quién sabe Python?", "conversation_history": []})
    assert r.status_code == 200
    data = r.json()
    assert "Respuesta sintética" in data["response"]
    assert data.get("model") == "gpt-4o-mini"
    assert len(data.get("sources") or []) >= 1


def test_chatbot_zero_chunks_uses_general_prompt(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _ZeroCount:
        count = 0

    class _KcLimit:
        def execute(self):
            return _ZeroCount()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    class _Msg:
        content = "Sin chunks, respuesta genérica."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, *_a, **_k):
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, *_a, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "Hola", "conversation_history": []})
    assert r.status_code == 200
    data = r.json()
    assert data.get("sources") == []
    assert "genérica" in data["response"] or "Sin chunks" in data["response"]


def test_chatbot_vector_search_error_still_returns_200(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _CountExec:
        count = 3

    class _KcLimit:
        def execute(self):
            return _CountExec()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    def _search_fail(**_kwargs):
        raise RuntimeError("vector rpc down")

    monkeypatch.setattr(api_module, "search_similar_chunks", _search_fail)

    class _Msg:
        content = "Podés reformular la pregunta."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, *_a, **_k):
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, *_a, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "Busco X", "conversation_history": []})
    assert r.status_code == 200
    data = r.json()
    assert data.get("sources") == []
    assert "reformular" in data["response"].lower()


def test_chatbot_generic_exception_returns_500(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        api_module,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(RuntimeError("rag fail")),
    )
    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "hola", "conversation_history": []})
    assert r.status_code == 500
    detail = r.json().get("detail", "")
    assert "rag fail" in detail or "Error en chatbot" in detail


def test_chatbot_tries_vector_thresholds_until_chunks_found(monkeypatch):
    """Bucle de thresholds 0.3 → 0.4 → 0.5 hasta obtener chunks (1447–1457)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _CountExec:
        count = 2

    class _KcLimit:
        def execute(self):
            return _CountExec()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())

    thresholds_seen: list[float] = []

    def _search(**kwargs):
        thresholds_seen.append(float(kwargs.get("match_threshold", 0)))
        if kwargs.get("match_threshold", 0) < 0.5:
            return []
        return [
            {
                "content": "Fragmento con threshold alto.",
                "entity_type": "candidate",
                "entity_id": "c1",
                "metadata": {"name": "Ana"},
            }
        ]

    monkeypatch.setattr(api_module, "search_similar_chunks", _search)

    class _Msg:
        content = "Respuesta con contexto."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, **_kwargs):
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "¿Algo?", "conversation_history": []})
    assert r.status_code == 200
    assert thresholds_seen == [0.3, 0.4, 0.5]
    data = r.json()
    assert len(data.get("sources") or []) >= 1


def test_chatbot_includes_conversation_history_in_openai_messages(monkeypatch):
    """Últimos mensajes del historial entran en `messages` (1533–1537)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _CountExec:
        count = 2

    class _KcLimit:
        def execute(self):
            return _CountExec()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(
        api_module,
        "search_similar_chunks",
        lambda **kwargs: [
            {
                "content": "Contexto RAG.",
                "entity_type": "candidate",
                "entity_id": "c1",
                "metadata": {},
            }
        ],
    )

    seen_messages: list = []

    class _Msg:
        content = "Respuesta con historial."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, **kwargs):
            seen_messages.append(kwargs.get("messages") or [])
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post(
        "/chatbot",
        json={
            "message": "Segunda pregunta",
            "conversation_history": [
                {"role": "user", "content": "Hola"},
                {"role": "assistant", "content": "Hola, ¿en qué ayudo?"},
            ],
        },
    )
    assert r.status_code == 200
    assert seen_messages, "debe llamarse chat.completions.create"
    flat = seen_messages[0]
    roles = [m.get("role") for m in flat if m.get("role") in ("user", "assistant")]
    assert "user" in roles and "assistant" in roles


def test_chatbot_chunks_exist_but_similar_search_empty_at_all_thresholds(monkeypatch):
    """Hay chunks en BD pero `search_similar_chunks` devuelve vacío en 0.3/0.4/0.5 (1461–1462)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-chatbot")

    class _CountExec:
        count = 3

    class _KcLimit:
        def execute(self):
            return _CountExec()

    class _KcSelect:
        def limit(self, _n):
            return _KcLimit()

    class _KcTable:
        def select(self, *_args, **_kwargs):
            return _KcSelect()

    class _Sb:
        def table(self, name):
            assert name == "knowledge_chunks"
            return _KcTable()

    monkeypatch.setattr(api_module, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(api_module, "search_similar_chunks", lambda **kwargs: [])

    class _Msg:
        content = "Sin coincidencias vectoriales."

    class _Choice:
        message = _Msg()

    class _OpenAIResp:
        choices = [_Choice()]
        model = "gpt-4o-mini"

    class _Completions:
        def create(self, **_kwargs):
            return _OpenAIResp()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

    client = TestClient(app)
    r = client.post("/chatbot", json={"message": "¿Algo raro?", "conversation_history": []})
    assert r.status_code == 200
    data = r.json()
    assert data.get("sources") == []
