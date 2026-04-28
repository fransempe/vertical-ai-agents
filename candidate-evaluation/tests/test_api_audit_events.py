"""Audit hooks emitted by automatic evaluation API flows."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import app, matching_runs  # noqa: E402


class _FakeMeetCrew:
    def kickoff(self):
        return {
            "meet_id": "550e8400-e29b-41d4-a716-446655440000",
            "candidate": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "Audit Test",
                "email": "audit@test.com",
            },
            "jd_interview": {"id": "550e8400-e29b-41d4-a716-446655440002", "interview_name": "Dev"},
            "match_evaluation": {
                "final_recommendation": "Recomendado",
                "justification": "Audit test",
                "is_potential_match": False,
                "compatibility_score": 91,
            },
            "conversation_analysis": {
                "emotion_sentiment_summary": {
                    "prosody_summary_text": "ok",
                    "burst_summary_text": "ok",
                }
            },
        }


class _FakeCvCrew:
    def kickoff(self):
        return '{"success": true, "email": "candidate@example.com"}'


class _FakeCvCrewRaises:
    def kickoff(self):
        raise RuntimeError("cv crew boom")


def test_read_cv_emits_one_success_audit_event(monkeypatch):
    captured_events = []

    async def _run_pool(fn):
        return fn()

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *args, **kwargs: _FakeCvCrew())
    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    monkeypatch.setattr(api_module, "record_cv_candidate_audit_event", _capture_audit)

    client = TestClient(app)
    response = client.post(
        "/read-cv",
        json={"filename": "folder/cv.pdf", "user_id": "user-1", "client_id": "client-1"},
    )

    assert response.status_code == 200
    assert len(captured_events) == 1
    assert captured_events[0]["action"] == "candidate_creation_from_cv"
    assert captured_events[0]["status"] == "success"
    assert captured_events[0]["filename"] == "folder/cv.pdf"
    assert captured_events[0]["metadata"]["candidate_status"] == "created"
    assert captured_events[0]["metadata"]["candidate_email"] == "candidate@example.com"
    assert captured_events[0]["metadata"]["user_id"] == "user-1"
    assert captured_events[0]["metadata"]["client_id"] == "client-1"


def test_read_cv_emits_one_failed_audit_event(monkeypatch):
    captured_events = []

    async def _run_pool(fn):
        return fn()

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-sk")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setattr(api_module, "create_cv_analysis_crew", lambda *args, **kwargs: _FakeCvCrewRaises())
    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    monkeypatch.setattr(api_module, "record_cv_candidate_audit_event", _capture_audit)

    client = TestClient(app)
    response = client.post("/read-cv", json={"filename": "folder/cv.pdf"})

    assert response.status_code == 500
    assert len(captured_events) == 1
    assert captured_events[0]["action"] == "candidate_creation_from_cv"
    assert captured_events[0]["status"] == "failed"
    assert captured_events[0]["filename"] == "folder/cv.pdf"
    assert "cv crew boom" in captured_events[0]["error_message"]


def test_evaluate_meet_emits_one_success_audit_event(monkeypatch):
    captured_events = []

    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    def _fake_save(_json_str: str) -> str:
        return json.dumps({"success": True, "evaluation_id": "audit-eval-1", "action": "created"})

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setattr(api_module, "create_single_meet_evaluation_crew", lambda mid: _FakeMeetCrew())
    monkeypatch.setattr(api_module, "save_meet_evaluation", _fake_save)
    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)
    monkeypatch.setattr(api_module, "record_evaluation_audit_event", _capture_audit)

    client = TestClient(app)
    response = client.post(
        "/evaluate-meet",
        json={"meet_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    assert response.status_code == 200
    assert len(captured_events) == 1
    assert captured_events[0]["action"] == "candidate_evaluation"
    assert captured_events[0]["status"] == "success"
    assert captured_events[0]["metadata"]["evaluation_id"] == "audit-eval-1"
    assert captured_events[0]["metadata"]["compatibility_score"] == 91


def _patch_run_pool(monkeypatch):
    async def _run_pool(fn, *args, **kwargs):
        if args:
            return fn(*args, **kwargs)
        return fn() if not kwargs else fn(**kwargs)

    monkeypatch.setattr(api_module, "run_in_threadpool", _run_pool)


def test_create_elevenlabs_agent_emits_one_success_audit_event(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440100"
    jd_row = {
        "id": jd_id,
        "job_description": "Descripción para auditoría " * 4,
        "interview_name": "Entrevista Audit",
        "client_id": "550e8400-e29b-41d4-a716-446655440101",
    }
    captured_events = []

    class _UpdateChain:
        def __init__(self, update_data):
            self.update_data = update_data

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return type("R", (), {"data": [{**jd_row, **self.update_data}]})()

    class _SelectChain:
        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, _limit):
            return self

        def execute(self):
            return type("R", (), {"data": [jd_row]})()

    class _JdTable:
        def select(self, *_cols):
            return _SelectChain()

        def update(self, update_data):
            return _UpdateChain(update_data)

    class _Supabase:
        def table(self, table_name):
            assert table_name == "jd_interviews"
            return _JdTable()

    class _ClientEmailTool:
        @staticmethod
        def func(client_id):
            return json.dumps({"email": "client@test.example", "name": "Audit Client", "client_id": client_id})

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-key")
    monkeypatch.setattr(api_module, "create_client", lambda _url, _key: _Supabase())
    monkeypatch.setattr(api_module, "get_client_email", _ClientEmailTool())
    monkeypatch.setattr(
        api_module,
        "create_elevenlabs_agent",
        lambda **_kwargs: {"agent_id": "audit-agent-1", "name": "Audit Agent"},
    )
    monkeypatch.setattr(api_module, "record_elevenlabs_agent_audit_event", _capture_audit)

    import tools.vector_tools as vector_tools

    monkeypatch.setattr(vector_tools, "index_jd_interview", lambda _row: None)
    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    response = client.post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})

    assert response.status_code == 200
    assert len(captured_events) == 1
    assert captured_events[0]["action"] == "elevenlabs_agent_creation"
    assert captured_events[0]["status"] == "success"
    assert captured_events[0]["jd_interview_id"] == jd_id
    assert captured_events[0]["metadata"]["agent_id"] == "audit-agent-1"
    assert captured_events[0]["metadata"]["agent_name"] == "Audit Agent"
    assert captured_events[0]["metadata"]["client_id"] == jd_row["client_id"]


def test_create_elevenlabs_agent_emits_one_failed_audit_event_for_http_errors(monkeypatch):
    jd_id = "550e8400-e29b-41d4-a716-446655440110"
    captured_events = []

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(api_module, "record_elevenlabs_agent_audit_event", _capture_audit)
    _patch_run_pool(monkeypatch)

    client = TestClient(app)
    response = client.post("/create-elevenlabs-agent", json={"jd_interview_id": jd_id})

    assert response.status_code == 500
    assert len(captured_events) == 1
    assert captured_events[0]["action"] == "elevenlabs_agent_creation"
    assert captured_events[0]["status"] == "failed"
    assert captured_events[0]["metadata"]["status_code"] == 500
    assert "Variables de entorno faltantes" in captured_events[0]["error_message"]


def test_match_candidates_does_not_audit_until_background_process_finishes(monkeypatch):
    fixed = uuid.UUID("00000000-0000-0000-0000-000000000123")
    captured_events = []

    def _noop_task(_run_id, _user_id, _client_id):
        return None

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setattr(api_module.uuid, "uuid4", lambda: fixed)
    monkeypatch.setattr(api_module, "do_matching_long_task", _noop_task)
    monkeypatch.setattr(api_module, "record_matching_audit_event", _capture_audit)

    try:
        client = TestClient(app)
        response = client.post("/match-candidates", json={"user_id": "user-1", "client_id": "client-1"})

        assert response.status_code == 202
        assert captured_events == []
    finally:
        matching_runs.pop(str(fixed), None)


def test_do_matching_long_task_emits_one_success_audit_event(monkeypatch):
    captured_events = []

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "record_matching_audit_event", _capture_audit)
    monkeypatch.setattr(
        api_module,
        "run_deterministic_matching",
        lambda **_kwargs: [{"candidate": {"id": "candidate-1"}, "matching_interviews": [{"id": "jd-1"}]}],
    )

    run_id = "audit-match-run-ok"
    try:
        api_module.do_matching_long_task(run_id, "user-1", "client-1")

        assert len(captured_events) == 1
        assert captured_events[0]["action"] == "candidate_matching"
        assert captured_events[0]["status"] == "success"
        assert captured_events[0]["metadata"]["user_id"] == "user-1"
        assert captured_events[0]["metadata"]["total_matches"] == 1
        assert matching_runs[run_id]["status"] == "done"
    finally:
        matching_runs.pop(run_id, None)


def test_do_matching_long_task_emits_one_failed_audit_event(monkeypatch):
    captured_events = []

    def _capture_audit(**kwargs):
        captured_events.append(kwargs)
        return True

    def _boom(**_kwargs):
        raise RuntimeError("matching audit boom")

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "record_matching_audit_event", _capture_audit)
    monkeypatch.setattr(api_module, "run_deterministic_matching", _boom)

    run_id = "audit-match-run-fail"
    try:
        api_module.do_matching_long_task(run_id, None, None)

        assert len(captured_events) == 1
        assert captured_events[0]["action"] == "candidate_matching"
        assert captured_events[0]["status"] == "failed"
        assert captured_events[0]["error_message"] == "matching audit boom"
        assert matching_runs[run_id]["status"] == "error"
    finally:
        matching_runs.pop(run_id, None)
