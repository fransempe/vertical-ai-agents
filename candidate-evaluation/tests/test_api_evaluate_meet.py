"""POST /evaluate-meet con crew, guardado y enriquecimiento mockeados."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app  # noqa: E402


def _fake_save_meet_evaluation(_json_str: str) -> str:
    return json.dumps({"success": True, "evaluation_id": "eval-test-1", "action": "created"})


class _FakeMeetCrew:
    def kickoff(self):
        return {
            "meet_id": "550e8400-e29b-41d4-a716-446655440000",
            "candidate": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "Test",
                "email": "t@test.com",
            },
            "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002", "interview_name": "Dev"},
            "match_evaluation": {
                "final_recommendation": "Condicional",
                "justification": "Unit test",
                "is_potential_match": False,
                "compatibility_score": 42,
            },
            "conversation_analysis": {
                "emotion_sentiment_summary": {
                    "prosody_summary_text": "ok",
                    "burst_summary_text": "ok",
                },
                "technical_assessment": {
                    "knowledge_level": "Medio",
                    "practical_experience": "2y",
                    "technical_questions": [],
                },
            },
        }


def test_evaluate_meet_success(monkeypatch):
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda mid: _FakeMeetCrew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    client = TestClient(app)
    r = client.post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["result"]["compatibility_score"] == 42
    assert data["result"]["is_potential_match"] is False


def test_evaluate_meet_enriches_from_get_meet_evaluation_data(monkeypatch):
    """Si el crew no devuelve candidate/jd ids, se rellenan con get_meet_evaluation_data."""

    class _CrewSparse:
        def kickoff(self):
            return {
                "meet_id": "550e8400-e29b-41d4-a716-446655440010",
                "candidate": {},
                "jd_interview": {},
                "match_evaluation": {
                    "final_recommendation": "No recomendado",
                    "justification": "Enrich test",
                    "is_potential_match": False,
                    "compatibility_score": 10,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                },
            }

    captured = []

    def _fake_save(json_str: str) -> str:
        captured.append(json.loads(json_str))
        return json.dumps({"success": True, "evaluation_id": "e1", "action": "created"})

    def _fake_get_meet(mid: str) -> str:
        return json.dumps(
            {
                "conversation": {
                    "candidate": {
                        "id": "550e8400-e29b-41d4-a716-446655440011",
                        "name": "Enriched",
                        "email": "e@test.example",
                    }
                },
                "jd_interview": {
                    "id": "550e8400-e29b-41d4-a716-446655440012",
                    "interview_name": "JD Name",
                    "job_description": "Desc",
                },
            }
        )

    class _MeetEvalTool:
        func = staticmethod(_fake_get_meet)

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda mid: _CrewSparse())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "get_meet_evaluation_data", _MeetEvalTool())

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    client = TestClient(app)
    mid = "550e8400-e29b-41d4-a716-446655440010"
    r = client.post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert captured, "save_meet_evaluation should have been called with enriched payload"
    saved = captured[0]
    assert saved["candidate"]["id"] == "550e8400-e29b-41d4-a716-446655440011"
    assert saved["jd_interview"]["id"] == "550e8400-e29b-41d4-a716-446655440012"


def _async_run_pool(monkeypatch):
    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)


def test_evaluate_meet_match_triggers_email_branch(monkeypatch):
    """is_potential_match True: consulta meets + conversations y marca email (sin POST real)."""
    mid = "550e8400-e29b-41d4-a716-446655440020"
    jd_id = "550e8400-e29b-41d4-a716-446655440021"

    class _CrewMatch:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {
                    "id": "550e8400-e29b-41d4-a716-446655440022",
                    "name": "Match",
                    "email": "m@example.com",
                    "tech_stack": ["Python"],
                },
                "jd_interview": {"id": jd_id, "interview_name": "Dev"},
                "match_evaluation": {
                    "final_recommendation": "Recomendado",
                    "justification": "Fit fuerte",
                    "is_potential_match": True,
                    "compatibility_score": 88,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                    "technical_assessment": {
                        "knowledge_level": "Alto",
                        "practical_experience": "5y",
                        "technical_questions": [],
                    },
                    "soft_skills": {},
                },
            }

    class _ConvExec:
        def execute(self):
            return type(
                "R", (), {"data": [{"conversation_data": {"messages": [{"role": "user", "content": "Hola"}]}}]}
            )()

    class _ConvEq:
        def eq(self, col, val):
            assert col == "meet_id" and val == mid
            return _ConvExec()

    class _ConvTable:
        def select(self, _cols):
            return _ConvEq()

    class _MeetExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "jd_interviews_id": jd_id,
                            "jd_interviews": {
                                "interview_name": "Python Dev",
                                "client_id": "cl-1",
                                "clients": {
                                    "email": "hiring@client.example",
                                    "name": "Cliente QA",
                                    "responsible": "Rec",
                                    "phone": "999",
                                },
                            },
                        }
                    ]
                },
            )()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExec()

    class _MeetSelect:
        def select(self, _q):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "meets":
                return _MeetSelect()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewMatch())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "Email enviado" in data["message"]
    assert data["result"]["is_potential_match"] is True


def test_evaluate_meet_match_email_formats_assistant_ai_and_other_roles(monkeypatch):
    """Roles `assistant` / `ai` / otros en el cuerpo del email (940–943)."""
    mid = "550e8400-e29b-41d4-a716-446655440560"
    jd_id = "550e8400-e29b-41d4-a716-446655440561"

    class _CrewMatch:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {
                    "id": "550e8400-e29b-41d4-a716-446655440562",
                    "name": "Match",
                    "email": "m@example.com",
                    "tech_stack": ["Python"],
                },
                "jd_interview": {"id": jd_id, "interview_name": "Dev"},
                "match_evaluation": {
                    "final_recommendation": "Recomendado",
                    "justification": "Fit",
                    "is_potential_match": True,
                    "compatibility_score": 90,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {"prosody_summary_text": "ok", "burst_summary_text": "ok"},
                    "technical_assessment": {
                        "knowledge_level": "Alto",
                        "practical_experience": "5y",
                        "technical_questions": [],
                    },
                    "soft_skills": {},
                },
            }

    class _ConvExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "conversation_data": {
                                "messages": [
                                    {"role": "user", "content": "Hola"},
                                    {"role": "assistant", "content": "Soy asistente"},
                                    {"role": "ai", "content": "Soy ai"},
                                    {"role": "system", "content": "Meta"},
                                ]
                            }
                        }
                    ]
                },
            )()

    class _ConvEq:
        def eq(self, col, val):
            assert col == "meet_id" and val == mid
            return _ConvExec()

    class _ConvTable:
        def select(self, _cols):
            return _ConvEq()

    class _MeetExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "jd_interviews_id": jd_id,
                            "jd_interviews": {
                                "interview_name": "Python Dev",
                                "client_id": "cl-1",
                                "clients": {
                                    "email": "hiring@client.example",
                                    "name": "Cliente QA",
                                    "responsible": "Rec",
                                    "phone": "999",
                                },
                            },
                        }
                    ]
                },
            )()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExec()

    class _MeetSelect:
        def select(self, _q):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "meets":
                return _MeetSelect()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewMatch())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Entrevistador" in r.json().get("message", "") or r.json()["status"] == "success"


def test_evaluate_meet_match_email_uses_conversation_data_string(monkeypatch):
    """`conversation_data` como string (945–946)."""
    mid = "550e8400-e29b-41d4-a716-446655440570"
    jd_id = "550e8400-e29b-41d4-a716-446655440571"

    class _CrewMatch:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {
                    "id": "550e8400-e29b-41d4-a716-446655440572",
                    "name": "Match",
                    "email": "m2@example.com",
                    "tech_stack": ["Go"],
                },
                "jd_interview": {"id": jd_id, "interview_name": "Dev"},
                "match_evaluation": {
                    "final_recommendation": "Sí",
                    "justification": "Ok",
                    "is_potential_match": True,
                    "compatibility_score": 80,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {"prosody_summary_text": "ok", "burst_summary_text": "ok"},
                    "technical_assessment": {
                        "knowledge_level": "Medio",
                        "practical_experience": "3y",
                        "technical_questions": [],
                    },
                    "soft_skills": {},
                },
            }

    class _ConvExec:
        def execute(self):
            return type("R", (), {"data": [{"conversation_data": "Transcripción plana del meet"}]})()

    class _ConvEq:
        def eq(self, col, val):
            assert col == "meet_id" and val == mid
            return _ConvExec()

    class _ConvTable:
        def select(self, _cols):
            return _ConvEq()

    class _MeetExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "jd_interviews_id": jd_id,
                            "jd_interviews": {
                                "interview_name": "Go Dev",
                                "client_id": "cl-2",
                                "clients": {
                                    "email": "hr@client.example",
                                    "name": "C",
                                    "responsible": "R",
                                    "phone": "1",
                                },
                            },
                        }
                    ]
                },
            )()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExec()

    class _MeetSelect:
        def select(self, _q):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "meets":
                return _MeetSelect()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewMatch())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_fetches_emotion_when_prosody_missing(monkeypatch):
    """Sin prosodia: primero conversations (emotion_analysis); luego flujo de email con segundo create_client."""
    mid = "550e8400-e29b-41d4-a716-446655440030"
    jd_id = "550e8400-e29b-41d4-a716-446655440031"
    emo_raw = {"scores": {"calm": 0.8}}

    class _CrewNoProsody:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {"id": "c1", "name": "E", "email": "e@e.com"},
                "jd_interview": {"id": jd_id},
                "match_evaluation": {
                    "final_recommendation": "R",
                    "justification": "J",
                    "is_potential_match": True,
                    "compatibility_score": 90,
                },
                "conversation_analysis": {"technical_assessment": {}},
            }

    captured_save = []

    def _capture_save(js: str) -> str:
        captured_save.append(json.loads(js))
        return json.dumps({"success": True, "evaluation_id": "e2", "action": "created"})

    class _EmoExec:
        def execute(self):
            return type("R", (), {"data": [{"emotion_analysis": emo_raw}]})()

    class _EmoLimit:
        def limit(self, _n):
            return _EmoExec()

    class _EmoOrd:
        def order(self, _col, desc=False):
            return _EmoLimit()

    class _EmoEq:
        def eq(self, col, val):
            assert col == "meet_id" and val == mid
            return _EmoOrd()

    class _EmoSel:
        def select(self, _cols):
            return _EmoEq()

    class _SbEmotion:
        def table(self, name):
            assert name == "conversations"
            return _EmoSel()

    class _ConvExec:
        def execute(self):
            return type("R", (), {"data": [{"conversation_data": {}}]})()

    class _ConvEq:
        def eq(self, col, val):
            assert col == "meet_id"
            return _ConvExec()

    class _ConvTable:
        def select(self, _cols):
            return _ConvEq()

    class _MeetExec:
        def execute(self):
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "jd_interviews_id": jd_id,
                            "jd_interviews": {
                                "interview_name": "Role",
                                "client_id": "c",
                                "clients": {
                                    "email": "x@y.com",
                                    "name": "N",
                                    "responsible": "R",
                                    "phone": "1",
                                },
                            },
                        }
                    ]
                },
            )()

    class _MeetEq:
        def eq(self, col, val):
            return _MeetExec()

    class _MeetSel:
        def select(self, _q):
            return _MeetEq()

    class _SbEmail:
        def table(self, name):
            if name == "meets":
                return _MeetSel()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    _n = [0]

    def _factory(u, k):
        _n[0] += 1
        return _SbEmotion() if _n[0] == 1 else _SbEmail()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewNoProsody())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _capture_save)
    monkeypatch.setattr(api_module, "create_client", _factory)
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert captured_save
    saved = captured_save[0]
    em = saved["conversation_analysis"]["emotion_sentiment_summary"]
    assert em.get("raw_emotion_analysis") == emo_raw


def test_evaluate_meet_no_prosody_without_supabase_skips_emotion_fetch(monkeypatch):
    """Sin URL de Supabase no se intenta el fetch de emotion_analysis; is_potential_match false evita email."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    mid = "550e8400-e29b-41d4-a716-446655440115"

    class _CrewBare:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {"id": "c1", "name": "N", "email": "e@e.com"},
                "jd_interview": {"id": "j1"},
                "match_evaluation": {
                    "final_recommendation": "X",
                    "justification": "Y",
                    "is_potential_match": False,
                    "compatibility_score": 50,
                },
                "conversation_analysis": {"technical_assessment": {}},
            }

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _CrewBare())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def _crew_match_base(mid: str, jd_id: str):
    """Resultado mínimo para activar rama de email con match."""

    return {
        "meet_id": mid,
        "candidate": {
            "id": "550e8400-e29b-41d4-a716-4466554400a0",
            "name": "M",
            "email": "m@example.com",
            "tech_stack": ["Py"],
        },
        "jd_interview": {"id": jd_id},
        "match_evaluation": {
            "final_recommendation": "R",
            "justification": "J",
            "is_potential_match": True,
            "compatibility_score": 80,
        },
        "conversation_analysis": {
            "emotion_sentiment_summary": {"prosody_summary_text": "p", "burst_summary_text": "b"},
            "technical_assessment": {"knowledge_level": "M", "practical_experience": "1y", "technical_questions": []},
            "soft_skills": {},
        },
    }


def _supabase_meet_plus_conv(
    mid: str, jd_id: str, *, client_email: str | None = "h@client.example", messages: list | None = None
):
    class _ConvExec:
        def execute(self):
            msgs = [] if messages is None else messages
            return type("R", (), {"data": [{"conversation_data": {"messages": msgs}}]})()

    class _ConvEq:
        def eq(self, col, val):
            assert col == "meet_id" and val == mid
            return _ConvExec()

    class _ConvTable:
        def select(self, _cols):
            return _ConvEq()

    class _MeetExec:
        def execute(self):
            clients = (
                {"name": "Sin email"}
                if client_email is None
                else {
                    "email": client_email,
                    "name": "Co",
                    "responsible": "R",
                    "phone": "1",
                }
            )
            row = {
                "jd_interviews_id": jd_id,
                "jd_interviews": {
                    "interview_name": "Role",
                    "client_id": "cl-x",
                    "clients": clients,
                },
            }
            return type("R", (), {"data": [row]})()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExec()

    class _MeetSelect:
        def select(self, _q):
            return _MeetEq()

    class _Sb:
        def table(self, name):
            if name == "meets":
                return _MeetSelect()
            if name == "conversations":
                return _ConvTable()
            raise AssertionError(name)

    return _Sb


def test_evaluate_meet_match_without_nested_jd_does_not_send_email(monkeypatch):
    mid = "550e8400-e29b-41d4-a716-4466554400b0"
    jd_id = "550e8400-e29b-41d4-a716-4466554400b1"

    class _Crew:
        def kickoff(self):
            return _crew_match_base(mid, jd_id)

    class _MeetExecNull:
        def execute(self):
            return type("R", (), {"data": [{"jd_interviews_id": jd_id, "jd_interviews": None}]})()

    class _MeetEqNull:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExecNull()

    class _MeetSelNull:
        def select(self, _q):
            return _MeetEqNull()

    class _SbMeetsOnly:
        def table(self, name):
            assert name == "meets"
            return _MeetSelNull()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _SbMeetsOnly())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Email enviado" not in r.json()["message"]


def test_evaluate_meet_match_without_client_email_does_not_send_email(monkeypatch):
    mid = "550e8400-e29b-41d4-a716-4466554400c0"
    jd_id = "550e8400-e29b-41d4-a716-4466554400c1"

    class _Crew:
        def kickoff(self):
            return _crew_match_base(mid, jd_id)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(
        api_module, "create_client", lambda u, k: _supabase_meet_plus_conv(mid, jd_id, client_email=None)()
    )
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Email enviado" not in r.json()["message"]


def test_evaluate_meet_match_render_email_template_error_still_200(monkeypatch):
    mid = "550e8400-e29b-41d4-a716-4466554400d0"
    jd_id = "550e8400-e29b-41d4-a716-4466554400d1"

    class _Crew:
        def kickoff(self):
            return _crew_match_base(mid, jd_id)

    def _boom(**_kwargs):
        raise RuntimeError("template error for test")

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _supabase_meet_plus_conv(mid, jd_id)())
    monkeypatch.setattr(api_module, "render_email_template", _boom)
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Email enviado" not in r.json()["message"]


def test_evaluate_meet_match_empty_messages_still_sends_email(monkeypatch):
    mid = "550e8400-e29b-41d4-a716-4466554400e0"
    jd_id = "550e8400-e29b-41d4-a716-4466554400e1"

    class _Crew:
        def kickoff(self):
            return _crew_match_base(mid, jd_id)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _supabase_meet_plus_conv(mid, jd_id, messages=[])())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Email enviado" in r.json()["message"]


def test_evaluate_meet_match_no_meet_rows_skips_email(monkeypatch):
    """Consulta a meets sin filas: no hay destinatario ni conversación para el email."""
    mid = "550e8400-e29b-41d4-a716-446655440110"
    jd_id = "550e8400-e29b-41d4-a716-446655440111"

    class _Crew:
        def kickoff(self):
            return _crew_match_base(mid, jd_id)

    class _MeetExecEmpty:
        def execute(self):
            return type("R", (), {"data": []})()

    class _MeetEq:
        def eq(self, col, val):
            assert col == "id" and val == mid
            return _MeetExecEmpty()

    class _MeetSel:
        def select(self, _q):
            return _MeetEq()

    class _SbMeetsEmpty:
        def table(self, name):
            assert name == "meets"
            return _MeetSel()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _SbMeetsEmpty())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert "Email enviado" not in r.json()["message"]


def test_evaluate_meet_crew_returns_markdown_json_in_raw(monkeypatch):
    """Crew devuelve objeto con .raw = string en bloque ```json ... ```."""
    payload = _FakeMeetCrew().kickoff()
    md = "```json\n" + json.dumps(payload) + "\n```"

    class _CrewMd:
        def kickoff(self):
            class _R:
                raw = md

            return _R()

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewMd())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["compatibility_score"] == 42


def test_evaluate_meet_crew_returns_dict_in_content_attribute(monkeypatch):
    """Rama hasattr(result, 'content') con dict (sin .raw dict)."""
    payload = _FakeMeetCrew().kickoff()

    class _CrewContent:
        def kickoff(self):
            class _R:
                content = payload

            return _R()

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewContent())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["compatibility_score"] == 42


def test_evaluate_meet_crew_returns_dict_in_raw_attribute(monkeypatch):
    """Rama hasattr(result, 'raw') con dict (CrewOutput-like)."""
    payload = _FakeMeetCrew().kickoff()

    class _CrewRawDict:
        def kickoff(self):
            class _R:
                raw = payload

            return _R()

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewRawDict())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["compatibility_score"] == 42


def test_evaluate_meet_crew_returns_json_string_in_content_only(monkeypatch):
    """Solo .content como string JSON (sin bloque markdown); usa json.loads directo."""
    payload = _FakeMeetCrew().kickoff()
    body = json.dumps(payload)

    class _CrewContentStr:
        def kickoff(self):
            class _R:
                content = body

            return _R()

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewContentStr())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["compatibility_score"] == 42


def test_evaluate_meet_crew_string_invalid_json_inner_parse_error(monkeypatch):
    """Rama except interna al parsear `{...}` que no es JSON válido (664–681)."""

    class _CrewBad:
        def kickoff(self):
            return '{"a": }'

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewBad())

    def _fake_save(_json_str: str) -> str:
        return json.dumps({"success": True, "evaluation_id": "e1", "action": "created"})

    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440400"},
    )
    assert r.status_code == 200


def test_evaluate_meet_crew_weird_object_uses_str_result(monkeypatch):
    """Rama result_str = str(result) cuando no hay .raw/.content (653)."""

    class _Weird:
        def __str__(self):
            return json.dumps(_FakeMeetCrew().kickoff())

    class _CrewWeird:
        def kickoff(self):
            return _Weird()

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _CrewWeird())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["compatibility_score"] == 42


def test_evaluate_meet_save_meet_evaluation_returns_failure(monkeypatch):
    def _fake_save(_json_str: str) -> str:
        return json.dumps({"success": False, "error": "persist failed"})

    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200


def test_evaluate_meet_save_meet_evaluation_raises_logs_and_continues(monkeypatch):
    def _fake_save(_json_str: str) -> str:
        raise RuntimeError("save boom")

    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200


def test_evaluate_meet_save_meet_evaluation_tool_unresolvable(monkeypatch):
    monkeypatch.setattr(api_module, "save_meet_evaluation", None)
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200


def test_evaluate_meet_merges_raw_emotion_when_summary_has_burst_but_no_raw(monkeypatch):
    """Supabase conversations: añade raw_emotion_analysis si falta (816–820)."""
    mid = "550e8400-e29b-41d4-a716-446655440555"

    class _Crew:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {"id": "c1", "name": "A", "email": "a@a.com"},
                "jd_interview": {"id": "j1", "interview_name": "Dev"},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "burst_summary_text": "algo",
                    },
                },
            }

    class _ConvExec:
        def execute(self):
            return type("R", (), {"data": [{"emotion_analysis": {"scores": [0.1]}}]})()

    class _Ord:
        def order(self, *_a, **_k):
            return _Lim()

    class _Lim:
        def limit(self, _n):
            return _ConvExec()

    class _Eq:
        def eq(self, *_a, **_k):
            return _Ord()

    class _ConvTable:
        def select(self, _c):
            return _Eq()

    class _Sb:
        def table(self, name):
            assert name == "conversations"
            return _ConvTable()

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "create_client", lambda u, k: _Sb())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_emotion_block_swallows_supabase_failure(monkeypatch):
    """Si falla create_client en el fallback de emotion_analysis, la API sigue OK (except 828–829)."""
    mid = "550e8400-e29b-41d4-a716-446655440666"

    class _Crew:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {"id": "c1", "name": "A", "email": "a@a.com"},
                "jd_interview": {"id": "j1", "interview_name": "Dev"},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": None,
                        "burst_summary_text": None,
                    },
                },
            }

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(
        api_module,
        "create_client",
        lambda u, k: (_ for _ in ()).throw(RuntimeError("emotion supabase path")),
    )
    _async_run_pool(monkeypatch)

    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_save_meet_evaluation_uses_wrapped_callable(monkeypatch):
    """Rama `hasattr(save_meet_evaluation, '__wrapped__')` en api."""
    captured: list[str] = []

    def _underlying(*args, **kwargs) -> str:
        payload = args[-1] if args else ""
        captured.append(str(payload)[:80])
        return json.dumps({"success": True, "evaluation_id": "w1", "action": "created"})

    class _FakeSaveTool:
        __wrapped__ = _underlying

    monkeypatch.setattr(api_module, "save_meet_evaluation", _FakeSaveTool())
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)

    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert captured, "debería llamarse __wrapped__"


def test_evaluate_meet_returns_500_when_crew_factory_raises(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "create_single_meet_evaluation_crew",
        lambda _mid: (_ for _ in ()).throw(RuntimeError("no crew")),
    )
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 500
    assert "no crew" in r.json().get("detail", "")


def test_evaluate_meet_kickoff_plain_string_no_json_detectable(monkeypatch):
    """Texto sin `{…}` parseable → full_result {} y 200 (671–675)."""

    class _Crew:
        def kickoff(self):
            return "solo texto sin llaves json"

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440777"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_kickoff_string_brace_extract_fails_json_loads(monkeypatch):
    """`{invalid}` detectado pero `json.loads` falla → 677–681."""

    class _Crew:
        def kickoff(self):
            return "{invalid}"

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440778"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_json_array_string_normalized_to_empty_dict(monkeypatch):
    """`json.loads` del kickoff devuelve lista → `full_result` se normaliza a `{}` (684–685)."""

    class _Crew:
        def kickoff(self):
            return '[{"meet_id": "550e8400-e29b-41d4-a716-446655440888"}]'

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _Crew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440888"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_evaluate_meet_enrich_uses_get_meet_evaluation_data_wrapped(monkeypatch):
    """Rama `get_meet_evaluation_data.__wrapped__` (701–702)."""
    mid = "550e8400-e29b-41d4-a716-446655440770"
    captured: list[dict] = []

    class _CrewSparse:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {},
                "jd_interview": {},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                },
            }

    def _wrapped(*args, **kwargs) -> str:
        mid_param = args[-1]
        assert mid_param == mid
        return json.dumps(
            {
                "conversation": {
                    "candidate": {
                        "id": "550e8400-e29b-41d4-a716-446655440771",
                        "name": "Wrapped",
                        "email": "w@test.example",
                    }
                },
                "jd_interview": {
                    "id": "550e8400-e29b-41d4-a716-446655440772",
                    "interview_name": "JD-W",
                    "job_description": "d",
                },
            }
        )

    class _MeetTool:
        __wrapped__ = _wrapped

    def _fake_save(json_str: str) -> str:
        captured.append(json.loads(json_str))
        return json.dumps({"success": True, "evaluation_id": "e-wrap", "action": "created"})

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _CrewSparse())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "get_meet_evaluation_data", _MeetTool())
    _async_run_pool(monkeypatch)
    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert captured[0]["candidate"]["id"] == "550e8400-e29b-41d4-a716-446655440771"


def test_evaluate_meet_enrich_uses_plain_callable_get_meet_evaluation_data(monkeypatch):
    """Rama `callable(...) and not hasattr(..., 'name')` (707–708)."""
    mid = "550e8400-e29b-41d4-a716-446655440773"
    captured: list[dict] = []

    class _CrewSparse:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {},
                "jd_interview": {},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                },
            }

    def _plain(mid_param: str) -> str:
        assert mid_param == mid
        return json.dumps(
            {
                "conversation": {
                    "candidate": {
                        "id": "550e8400-e29b-41d4-a716-446655440774",
                        "name": "Plain",
                        "email": "p@test.example",
                    }
                },
                "jd_interview": {
                    "id": "550e8400-e29b-41d4-a716-446655440775",
                    "interview_name": "JD-P",
                    "job_description": "d",
                },
            }
        )

    def _fake_save(json_str: str) -> str:
        captured.append(json.loads(json_str))
        return json.dumps({"success": True, "evaluation_id": "e-plain", "action": "created"})

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _CrewSparse())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "get_meet_evaluation_data", _plain)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert captured[0]["candidate"]["id"] == "550e8400-e29b-41d4-a716-446655440774"


def test_evaluate_meet_save_meet_evaluation_uses_dot_func(monkeypatch):
    """Rama `save_meet_evaluation.func` (844–845)."""
    captured: list[str] = []

    def _impl(*args, **kwargs) -> str:
        payload = args[-1]
        captured.append(str(payload)[:80])
        return json.dumps({"success": True, "evaluation_id": "e-dot-func", "action": "created"})

    class _SaveTool:
        func = _impl

    monkeypatch.setattr(api_module, "save_meet_evaluation", _SaveTool())
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert captured


def test_evaluate_meet_save_meet_evaluation_uses_dot_underscore_func(monkeypatch):
    """Rama `save_meet_evaluation._func` (846–847)."""
    captured: list[str] = []

    def _impl(*args, **kwargs) -> str:
        payload = args[-1]
        captured.append(str(payload)[:80])
        return json.dumps({"success": True, "evaluation_id": "e-us-func", "action": "created"})

    class _SaveTool:
        _func = _impl

    monkeypatch.setattr(api_module, "save_meet_evaluation", _SaveTool())
    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _mid: _FakeMeetCrew())
    _async_run_pool(monkeypatch)
    r = TestClient(app).post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert r.status_code == 200
    assert captured


def test_evaluate_meet_enrich_uses_get_meet_evaluation_data_dunder_func(monkeypatch):
    """Rama `get_meet_evaluation_data._func` (705–706)."""
    mid = "550e8400-e29b-41d4-a716-446655440779"
    captured: list[dict] = []

    class _CrewSparse:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {},
                "jd_interview": {},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                },
            }

    def _func(meet_param: str) -> str:
        assert meet_param == mid
        return json.dumps(
            {
                "conversation": {
                    "candidate": {
                        "id": "550e8400-e29b-41d4-a716-446655440780",
                        "name": "ViaFunc",
                        "email": "vf@test.example",
                    }
                },
                "jd_interview": {
                    "id": "550e8400-e29b-41d4-a716-446655440781",
                    "interview_name": "JD",
                    "job_description": "d",
                },
            }
        )

    # Solo `_func` (sin `.func`) para cubrir la rama 705–706; SimpleNamespace evita atributos de Tool.
    _meet_tool = SimpleNamespace(_func=_func)

    def _fake_save(json_str: str) -> str:
        captured.append(json.loads(json_str))
        return json.dumps({"success": True, "evaluation_id": "e-dunder", "action": "created"})

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _CrewSparse())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "get_meet_evaluation_data", _meet_tool)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert captured, "save_meet_evaluation debería recibir payload enriquecido"
    assert captured[0]["candidate"]["id"] == "550e8400-e29b-41d4-a716-446655440780"


def test_evaluate_meet_enrich_exception_still_returns_200(monkeypatch):
    """745–747: fallo al enriquecer no tumba la respuesta."""
    mid = "550e8400-e29b-41d4-a716-446655440782"

    class _CrewSparse:
        def kickoff(self):
            return {
                "meet_id": mid,
                "candidate": {},
                "jd_interview": {},
                "match_evaluation": {
                    "final_recommendation": "No",
                    "justification": "t",
                    "is_potential_match": False,
                    "compatibility_score": 0,
                },
                "conversation_analysis": {
                    "emotion_sentiment_summary": {
                        "prosody_summary_text": "ok",
                        "burst_summary_text": "ok",
                    },
                },
            }

    def _boom(_mid):
        raise RuntimeError("enrich fail")

    _meet_tool = SimpleNamespace(_func=_boom)

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda _m: _CrewSparse())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save_meet_evaluation)
    monkeypatch.setattr(api_module, "get_meet_evaluation_data", _meet_tool)
    _async_run_pool(monkeypatch)
    r = TestClient(app).post("/evaluate-meet", json={"meet_id": mid})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
