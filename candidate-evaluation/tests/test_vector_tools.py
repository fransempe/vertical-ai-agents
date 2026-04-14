"""Tests unitarios básicos para tools.vector_tools."""

import json

import pytest

from tools import vector_tools


def test_get_supabase_client_raises_without_env(monkeypatch):
    monkeypatch.setattr(vector_tools, "SUPABASE_URL", None)
    monkeypatch.setattr(vector_tools, "SUPABASE_KEY", None)

    with pytest.raises(ValueError, match="SUPABASE_URL y SUPABASE_KEY"):
        vector_tools.get_supabase_client()


def test_generate_embedding_raises_when_openai_unavailable(monkeypatch):
    monkeypatch.setattr(vector_tools, "OPENAI_AVAILABLE", False)
    monkeypatch.setattr(vector_tools, "openai_client", None)

    with pytest.raises(ValueError, match="OpenAI no está disponible"):
        vector_tools.generate_embedding("hola mundo")


def test_generate_embedding_success(monkeypatch):
    class _Emb:
        def create(self, model, input):
            return type("Resp", (), {"data": [type("Item", (), {"embedding": [0.25, 0.5, 0.75]})()]})()

    class _Client:
        embeddings = _Emb()

    monkeypatch.setattr(vector_tools, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(vector_tools, "openai_client", _Client())

    emb = vector_tools.generate_embedding("texto", model="text-embedding-3-small")
    assert emb == [0.25, 0.5, 0.75]


def test_generate_embedding_propagates_openai_api_error(monkeypatch):
    class _Emb:
        def create(self, model, input):
            raise RuntimeError("rate limit")

    class _Client:
        embeddings = _Emb()

    monkeypatch.setattr(vector_tools, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(vector_tools, "openai_client", _Client())

    with pytest.raises(RuntimeError, match="rate limit"):
        vector_tools.generate_embedding("x")


def test_insert_knowledge_chunk_returns_string_id(monkeypatch):
    class _Exec:
        data = "chunk-abc"

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            assert name == "insert_knowledge_chunk"
            assert params["p_entity_type"] == "candidate"
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    cid = vector_tools.insert_knowledge_chunk("contenido", [0.1, 0.2], "candidate", None, None)
    assert cid == "chunk-abc"


def test_search_similar_chunks_uses_embedding_and_rpc(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model: [0.0, 0.1])

    class _Exec:
        data = [{"id": "c1", "similarity": 0.9}]

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            assert name == "search_similar_chunks"
            assert params["match_threshold"] == 0.7
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    out = vector_tools.search_similar_chunks("busco esto", match_count=5)
    assert len(out) == 1
    assert out[0]["id"] == "c1"


def test_delete_knowledge_chunks_int_result(monkeypatch):
    class _Exec:
        data = 4

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            assert name == "delete_knowledge_chunks"
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.delete_knowledge_chunks("e1", "candidate") == 4


def test_delete_knowledge_chunks_dict_result(monkeypatch):
    class _Exec:
        data = {"delete_knowledge_chunks": 2}

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.delete_knowledge_chunks("e1", "jd_interview") == 2


def test_update_knowledge_chunk_rpc_string_id(monkeypatch):
    class _Exec:
        data = "rpc-chunk-1"

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            assert name == "update_knowledge_chunk"
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.update_knowledge_chunk("e1", "candidate", "txt", [0.1], None) == "rpc-chunk-1"


def test_update_knowledge_chunk_rpc_dict_id(monkeypatch):
    class _Exec:
        data = {"id": "rpc-chunk-2"}

    class _Rpc:
        def execute(self):
            return _Exec()

    class _Sb:
        def rpc(self, name, params):
            return _Rpc()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.update_knowledge_chunk("e1", "candidate", "txt", [0.1], {"k": 1}) == "rpc-chunk-2"


def test_update_knowledge_chunk_manual_update_when_rpc_fails(monkeypatch):
    class _KCSelect:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "row-99"}]})()

    class _KCUpdate:
        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "row-99"}]})()

    class _KCTable:
        def select(self, _cols):
            return _KCSelect()

        def update(self, _data):
            return _KCUpdate()

        def insert(self, _data):
            raise AssertionError("no insert when row exists")

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("rpc unavailable")

        def table(self, name):
            assert name == "knowledge_chunks"
            return _KCTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.update_knowledge_chunk("e1", "candidate", "new", [0.2], None) == "row-99"


def test_update_knowledge_chunk_manual_insert_when_rpc_returns_no_id(monkeypatch):
    class _ExecRpc:
        data = {}

    class _Rpc:
        def execute(self):
            return _ExecRpc()

    class _KCSelect:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _KCInsert:
        def execute(self):
            return type("R", (), {"data": [{"id": "new-row"}]})()

    class _KCTable:
        def select(self, _cols):
            return _KCSelect()

        def update(self, _data):
            raise AssertionError("no update when no row")

        def insert(self, _data):
            return _KCInsert()

    class _Sb:
        def rpc(self, *_a, **_k):
            return _Rpc()

        def table(self, name):
            assert name == "knowledge_chunks"
            return _KCTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    assert vector_tools.update_knowledge_chunk("e2", "jd", "body", [0.3], {"m": 2}) == "new-row"


def test_index_candidate_delegates_to_embedding_and_update(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.1, 0.2])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "chunk-cand")

    obs = json.dumps(
        {
            "work_experience": [{"position": "Dev", "company": "ACME", "period": "2020-2022"}],
            "industries_and_sectors": [{"industry": "IT"}],
            "languages": [{"language": "EN", "level": "B2"}],
            "certifications_and_courses": [{"name": "AWS"}],
        }
    )
    cid = vector_tools.index_candidate(
        {
            "id": "c1",
            "name": "Ana",
            "email": "a@a.com",
            "tech_stack": ["python", "go"],
            "observations": obs,
        }
    )
    assert cid == "chunk-cand"


def test_index_jd_interview_truncates_long_job_description(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.5])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "chunk-jd")

    long_jd = "x" * 250
    cid = vector_tools.index_jd_interview(
        {
            "id": "jd1",
            "interview_name": "Backend",
            "job_description": long_jd,
            "tech_stack": "python, go",
            "agent_id": "ag1",
            "status": "active",
        }
    )
    assert cid == "chunk-jd"


def test_index_all_candidates_counts_successes(monkeypatch):
    rows = [
        {
            "id": "1",
            "name": "A",
            "email": "a@a",
            "phone": None,
            "cv_url": None,
            "tech_stack": None,
            "observations": None,
            "created_at": None,
        },
        {
            "id": "2",
            "name": "B",
            "email": "b@b",
            "phone": None,
            "cv_url": None,
            "tech_stack": None,
            "observations": None,
            "created_at": None,
        },
    ]

    class _Lim:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _Sel:
        def limit(self, n):
            assert n == 1000
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", lambda c: "ok")
    assert vector_tools.index_all_candidates(limit=None) == 2


def test_index_all_jd_interviews_counts_successes(monkeypatch):
    rows = [
        {
            "id": "jd1",
            "interview_name": "X",
            "agent_id": None,
            "job_description": "d",
            "tech_stack": None,
            "client_id": None,
            "status": "active",
            "created_at": None,
        }
    ]

    class _Eq:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _Sel:
        def eq(self, _f, _v):
            return _Eq()

    class _JdTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            assert name == "jd_interviews"
            return _JdTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda j: "jid")
    assert vector_tools.index_all_jd_interviews() == 1


def test_index_meet_builds_content_and_upserts(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.9])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "chunk-meet")

    meet = {
        "id": "m1",
        "candidate_id": "c1",
        "jd_interviews_id": "jd1",
        "status": "done",
        "scheduled_at": "2025-01-01",
        "candidates": {"name": "Bo", "email": "b@b.com", "tech_stack": "go, rust"},
        "jd_interviews": {"id": "jd1", "interview_name": "Backend", "tech_stack": ["go"]},
    }
    assert vector_tools.index_meet(meet) == "chunk-meet"


def test_index_meet_evaluation_includes_alerts_and_match(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.1])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "chunk-meval")

    evaluation = {
        "id": "mev1",
        "meet_id": "m1",
        "candidate_id": "c1",
        "jd_interview_id": "jd1",
        "technical_assessment": {
            "knowledge_level": "Alto",
            "practical_experience": "5y",
            "technical_questions": [{"q": 1}, {"q": 2}],
        },
        "completeness_summary": {"overall_completeness": "Completa"},
        "alerts": [{"message": "Alerta A"}, "raw"],
        "match_evaluation": {"score": 88, "summary": "Buen fit"},
        "created_at": "t0",
        "updated_at": "t1",
    }
    assert vector_tools.index_meet_evaluation(evaluation) == "chunk-meval"


def test_index_all_meets_respects_limit(monkeypatch):
    row = {
        "id": "m1",
        "candidate_id": "c1",
        "jd_interviews_id": "jd1",
        "status": "scheduled",
        "candidates": None,
        "jd_interviews": None,
    }

    class _Q:
        def __init__(self):
            self._lim = None

        def limit(self, n):
            self._lim = n
            return self

        def execute(self):
            assert self._lim == 3
            return type("R", (), {"data": [row]})()

    class _MeetTable:
        def select(self, _s):
            return _Q()

    class _Sb:
        def table(self, name):
            assert name == "meets"
            return _MeetTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet", lambda m: "x")
    assert vector_tools.index_all_meets(limit=3) == 1


def test_index_all_meets_without_limit(monkeypatch):
    row = {"id": "m2", "candidate_id": "c", "jd_interviews_id": "j", "status": "x"}

    class _Q:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _MeetTable:
        def select(self, _s):
            return _Q()

    class _Sb:
        def table(self, name):
            return _MeetTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet", lambda m: "y")
    assert vector_tools.index_all_meets(limit=None) == 1


def test_index_all_meet_evaluations_with_limit(monkeypatch):
    row = {"id": "e1", "meet_id": "m1", "candidate_id": "c1", "jd_interview_id": "j1"}

    class _Q:
        def __init__(self):
            self.limited = False

        def limit(self, n):
            assert n == 5
            self.limited = True
            return self

        def execute(self):
            assert self.limited
            return type("R", (), {"data": [row]})()

    class _Table:
        def select(self, _star):
            return _Q()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _Table()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet_evaluation", lambda e: "z")
    assert vector_tools.index_all_meet_evaluations(limit=5) == 1


def test_index_all_meet_evaluations_without_limit(monkeypatch):
    row = {"id": "e2", "meet_id": "m2", "candidate_id": "c2", "jd_interview_id": "j2"}

    class _Q:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _Table:
        def select(self, _star):
            return _Q()

    class _Sb:
        def table(self, name):
            return _Table()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet_evaluation", lambda e: "w")
    assert vector_tools.index_all_meet_evaluations(limit=None) == 1


def test_index_candidate_jd_status_builds_chunk(monkeypatch):
    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.3])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "cjs-1")

    record = {
        "id": "rel1",
        "candidate_id": "c1",
        "jd_interview_id": "j1",
        "status": "applied",
        "created_at": "2024-01-01",
        "candidates": {"name": "Bo", "email": "b@b.com"},
        "jd_interviews": {"interview_name": "BE", "tech_stack": "go, rust"},
    }
    assert vector_tools.index_candidate_jd_status(record) == "cjs-1"


def test_index_all_candidate_jd_status_with_limit(monkeypatch):
    row = {
        "id": "r1",
        "candidate_id": "c1",
        "jd_interview_id": "j1",
        "status": "x",
        "candidates": None,
        "jd_interviews": None,
    }

    class _Q:
        def __init__(self):
            self.n = None

        def limit(self, n):
            self.n = n
            return self

        def execute(self):
            assert self.n == 7
            return type("R", (), {"data": [row]})()

    class _Table:
        def select(self, _s):
            return _Q()

    class _Sb:
        def table(self, name):
            assert name == "candidate_jd_status"
            return _Table()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate_jd_status", lambda r: "ok")
    assert vector_tools.index_all_candidate_jd_status(limit=7) == 1


def test_index_all_candidate_jd_status_without_limit(monkeypatch):
    row = {
        "id": "r-all",
        "candidate_id": "c1",
        "jd_interview_id": "j1",
        "status": "open",
        "candidates": None,
        "jd_interviews": None,
    }

    class _Query:
        def execute(self):
            return type("R", (), {"data": [row]})()

    class _Table:
        def select(self, _s):
            return _Query()

    class _Sb:
        def table(self, name):
            assert name == "candidate_jd_status"
            return _Table()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate_jd_status", lambda r: "idx")
    assert vector_tools.index_all_candidate_jd_status(limit=None) == 1


def test_index_all_candidate_jd_status_continues_on_row_error(monkeypatch):
    rows = [
        {"id": "bad", "candidate_id": "c1", "jd_interview_id": "j1"},
        {"id": "good", "candidate_id": "c2", "jd_interview_id": "j2"},
    ]

    class _Query:
        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": rows})()

    class _Table:
        def select(self, _s):
            return _Query()

    class _Sb:
        def table(self, name):
            return _Table()

    def _idx(r):
        if r["id"] == "bad":
            raise ValueError("index fail")
        return "ok"

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate_jd_status", _idx)
    assert vector_tools.index_all_candidate_jd_status(limit=10) == 1


def test_get_supabase_client_calls_create_client_with_env(monkeypatch):
    """38: `create_client(SUPABASE_URL, SUPABASE_KEY)` cuando hay env."""
    monkeypatch.setattr(vector_tools, "SUPABASE_URL", "http://sb.test")
    monkeypatch.setattr(vector_tools, "SUPABASE_KEY", "secret")

    def _fake_create(url, key):
        assert url == "http://sb.test"
        assert key == "secret"
        return "supabase-client"

    monkeypatch.setattr(vector_tools, "create_client", _fake_create)
    assert vector_tools.get_supabase_client() == "supabase-client"


def test_insert_knowledge_chunk_propagates_rpc_error(monkeypatch):
    """112–114: excepción en RPC → log y re-lanzar."""

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("rpc insert fail")

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    with pytest.raises(RuntimeError, match="rpc insert fail"):
        vector_tools.insert_knowledge_chunk("c", [0.1], "candidate")


def test_generate_embedding_logs_and_propagates_on_openai_error(monkeypatch):
    """66–68: `except` en `generate_embedding`."""

    class _Emb:
        def create(self, model, input):
            raise RuntimeError("openai boom")

    class _Client:
        embeddings = _Emb()

    monkeypatch.setattr(vector_tools, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(vector_tools, "openai_client", _Client())
    with pytest.raises(RuntimeError, match="openai boom"):
        vector_tools.generate_embedding("x")


def test_update_knowledge_chunk_outer_exception_on_manual_update(monkeypatch):
    """196–198: fallo en `update().execute()` tras RPC caído."""

    class _KCSelect:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "kc-x"}]})()

    class _KCUpdate:
        def eq(self, *_a, **_k):
            return self

        def execute(self):
            raise RuntimeError("update execute fail")

    class _KCTable:
        def select(self, _cols):
            return _KCSelect()

        def update(self, _data):
            return _KCUpdate()

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("rpc down")

        def table(self, name):
            assert name == "knowledge_chunks"
            return _KCTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    with pytest.raises(RuntimeError, match="update execute fail"):
        vector_tools.update_knowledge_chunk("e1", "candidate", "txt", [0.1], None)


def test_update_knowledge_chunk_manual_insert_persists_metadata(monkeypatch):
    """188–189: insert manual con `metadata` cuando el RPC no devuelve id."""

    class _ExecRpc:
        data = {}

    class _Rpc:
        def execute(self):
            return _ExecRpc()

    class _KCSelect:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    captured = {}

    class _KCInsert:
        def execute(self):
            return type("R", (), {"data": [{"id": "new-meta"}]})()

    class _KCTable:
        def select(self, _cols):
            return _KCSelect()

        def insert(self, data):
            captured["metadata"] = data.get("metadata")
            return _KCInsert()

    class _Sb:
        def rpc(self, *_a, **_k):
            return _Rpc()

        def table(self, name):
            assert name == "knowledge_chunks"
            return _KCTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    out = vector_tools.update_knowledge_chunk("e-meta", "candidate", "body", [0.1], {"k": "v"})
    assert out == "new-meta"
    assert captured.get("metadata") == {"k": "v"}


def test_update_knowledge_chunk_manual_update_includes_metadata(monkeypatch):
    """174–175: update manual con `metadata` cuando el RPC falla."""

    class _KCSelect:
        def eq(self, *_a, **_k):
            return self

        def limit(self, _n):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "kc-1"}]})()

    captured = {}

    class _KCUpdate:
        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "kc-1"}]})()

    class _KCTable:
        def select(self, _cols):
            return _KCSelect()

        def update(self, data):
            captured["metadata"] = data.get("metadata")
            return _KCUpdate()

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("no rpc")

        def table(self, name):
            assert name == "knowledge_chunks"
            return _KCTable()

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    out = vector_tools.update_knowledge_chunk("e1", "candidate", "txt", [0.1], {"role": "x"})
    assert out == "kc-1"
    assert captured.get("metadata") == {"role": "x"}


def test_search_similar_chunks_propagates_error(monkeypatch):
    """245–247: fallo tras `generate_embedding` / Supabase."""

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda *a, **k: [0.0, 0.1])

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("search rpc")

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    with pytest.raises(RuntimeError, match="search rpc"):
        vector_tools.search_similar_chunks("query")


def test_delete_knowledge_chunks_propagates_error(monkeypatch):
    """278–280."""

    class _Sb:
        def rpc(self, *_a, **_k):
            raise RuntimeError("delete rpc")

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    with pytest.raises(RuntimeError, match="delete rpc"):
        vector_tools.delete_knowledge_chunks("e1", "candidate")


def test_index_candidate_propagates_error(monkeypatch):
    """365–367."""

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("emb")))
    with pytest.raises(RuntimeError, match="emb"):
        vector_tools.index_candidate({"id": "c1", "name": "A", "email": "a@a", "tech_stack": [], "observations": None})


def test_index_jd_interview_tech_stack_list_join(monkeypatch):
    """388–393: `tech_stack` como lista → `', '.join(...)`."""

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.1])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "jd-list")

    cid = vector_tools.index_jd_interview(
        {
            "id": "jdL",
            "interview_name": "Data",
            "job_description": "short",
            "tech_stack": ["python", "sql"],
            "status": "active",
        }
    )
    assert cid == "jd-list"


def test_index_jd_interview_propagates_error(monkeypatch):
    """437–439."""

    monkeypatch.setattr(
        vector_tools, "generate_embedding", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("jd emb"))
    )
    with pytest.raises(RuntimeError, match="jd emb"):
        vector_tools.index_jd_interview({"id": "j", "interview_name": "X"})


def test_index_all_candidates_skips_failed_candidate(monkeypatch):
    """481–483: un candidato lanza → `continue` y cuenta el resto."""

    rows = [
        {
            "id": "bad",
            "name": "B",
            "email": "b@b",
            "phone": None,
            "cv_url": None,
            "tech_stack": None,
            "observations": None,
            "created_at": None,
        },
        {
            "id": "good",
            "name": "G",
            "email": "g@g",
            "phone": None,
            "cv_url": None,
            "tech_stack": None,
            "observations": None,
            "created_at": None,
        },
    ]

    class _Lim:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _Sel:
        def limit(self, _n):
            return _Lim()

    class _CandTable:
        def select(self, _star):
            return _Sel()

    class _Sb:
        def table(self, name):
            assert name == "candidates"
            return _CandTable()

    def _idx(c):
        if c["id"] == "bad":
            raise ValueError("index one fail")
        return "ok"

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_candidate", _idx)
    assert vector_tools.index_all_candidates(limit=None) == 1


def test_index_all_candidates_outer_exception(monkeypatch):
    """488–490."""

    def _boom():
        raise RuntimeError("table missing")

    monkeypatch.setattr(vector_tools, "get_supabase_client", _boom)
    with pytest.raises(RuntimeError, match="table missing"):
        vector_tools.index_all_candidates()


def test_index_all_jd_interviews_skips_failed_row(monkeypatch):
    """529–531."""

    rows = [
        {
            "id": "jbad",
            "interview_name": "A",
            "agent_id": None,
            "job_description": "d",
            "tech_stack": None,
            "client_id": None,
            "status": "active",
            "created_at": None,
        },
        {
            "id": "jgood",
            "interview_name": "B",
            "agent_id": None,
            "job_description": "d",
            "tech_stack": None,
            "client_id": None,
            "status": "active",
            "created_at": None,
        },
    ]

    class _Eq:
        def execute(self):
            return type("R", (), {"data": rows})()

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

    def _idx(j):
        if j["id"] == "jbad":
            raise ValueError("jd fail")
        return "ok"

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_jd_interview", _idx)
    assert vector_tools.index_all_jd_interviews() == 1


def test_index_all_jd_interviews_outer_exception(monkeypatch):
    """536–538."""

    def _boom():
        raise RuntimeError("no jd table")

    monkeypatch.setattr(vector_tools, "get_supabase_client", _boom)
    with pytest.raises(RuntimeError, match="no jd table"):
        vector_tools.index_all_jd_interviews()


def test_index_meet_tech_stacks_as_lists(monkeypatch):
    """564, 571: candidato con lista; JD con string separado por comas (569)."""

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.2])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "m-list")

    meet = {
        "id": "mL",
        "status": "x",
        "candidates": {"name": "A", "email": "a@a", "tech_stack": ["go", "py"]},
        "jd_interviews": {"interview_name": "J", "tech_stack": "k8s, docker"},
    }
    assert vector_tools.index_meet(meet) == "m-list"


def test_index_meet_propagates_error(monkeypatch):
    """625–627."""

    monkeypatch.setattr(
        vector_tools, "generate_embedding", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("meet emb"))
    )
    with pytest.raises(RuntimeError, match="meet emb"):
        vector_tools.index_meet({"id": "m"})


def test_index_all_meets_skips_row_error(monkeypatch):
    """659–664."""

    rows = [{"id": "m1"}, {"id": "m2"}]

    class _Q:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _MeetTable:
        def select(self, _s):
            return _Q()

    class _Sb:
        def table(self, name):
            return _MeetTable()

    def _im(m):
        if m["id"] == "m1":
            raise ValueError("meet row fail")
        return "ok"

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet", _im)
    assert vector_tools.index_all_meets() == 1


def test_index_all_meets_outer_exception(monkeypatch):
    """672–676."""

    def _boom():
        raise RuntimeError("meets query fail")

    monkeypatch.setattr(vector_tools, "get_supabase_client", _boom)
    with pytest.raises(RuntimeError, match="meets query fail"):
        vector_tools.index_all_meets()


def test_index_meet_evaluation_propagates_error(monkeypatch):
    """781–785."""

    monkeypatch.setattr(
        vector_tools, "generate_embedding", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("mev emb"))
    )
    with pytest.raises(RuntimeError, match="mev emb"):
        vector_tools.index_meet_evaluation({"id": "e"})


def test_index_all_meet_evaluations_skips_row_error(monkeypatch):
    """816–821."""

    rows = [{"id": "e1"}, {"id": "e2"}]

    class _Q:
        def execute(self):
            return type("R", (), {"data": rows})()

    class _Table:
        def select(self, _star):
            return _Q()

    class _Sb:
        def table(self, name):
            assert name == "meet_evaluations"
            return _Table()

    def _idx(e):
        if e["id"] == "e1":
            raise ValueError("mev fail")
        return "z"

    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: _Sb())
    monkeypatch.setattr(vector_tools, "index_meet_evaluation", _idx)
    assert vector_tools.index_all_meet_evaluations() == 1


def test_index_all_meet_evaluations_outer_exception(monkeypatch):
    """829–834."""

    def _boom():
        raise RuntimeError("mev table fail")

    monkeypatch.setattr(vector_tools, "get_supabase_client", _boom)
    with pytest.raises(RuntimeError, match="mev table fail"):
        vector_tools.index_all_meet_evaluations()


def test_index_candidate_jd_status_jd_tech_as_list(monkeypatch):
    """868: `jd_tech` lista (rama `else`)."""

    monkeypatch.setattr(vector_tools, "generate_embedding", lambda text, model="text-embedding-3-small": [0.4])
    monkeypatch.setattr(vector_tools, "update_knowledge_chunk", lambda **kwargs: "cjs-list")

    record = {
        "id": "rL",
        "candidate_id": "c1",
        "jd_interview_id": "j1",
        "status": "open",
        "jd_interviews": {"interview_name": "FE", "tech_stack": ["react", "ts"]},
    }
    assert vector_tools.index_candidate_jd_status(record) == "cjs-list"


def test_index_candidate_jd_status_propagates_error(monkeypatch):
    """920–925."""

    monkeypatch.setattr(
        vector_tools, "generate_embedding", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cjs emb"))
    )
    with pytest.raises(RuntimeError, match="cjs emb"):
        vector_tools.index_candidate_jd_status({"id": "r"})


def test_index_all_candidate_jd_status_outer_exception(monkeypatch):
    """973–978."""

    def _boom():
        raise RuntimeError("cjs query fail")

    monkeypatch.setattr(vector_tools, "get_supabase_client", _boom)
    with pytest.raises(RuntimeError, match="cjs query fail"):
        vector_tools.index_all_candidate_jd_status()
