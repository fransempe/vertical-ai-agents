"""Evaluation jobs worker API."""

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import AnalysisResponse, app  # noqa: E402


class _Exec:
    def __init__(self, data=None):
        self.data = data

    def execute(self):
        return self


class _UpdateEq:
    def __init__(self, updates):
        self.updates = updates

    def eq(self, column, value):
        self.column = column
        self.value = value
        return _Exec([])


class _Table:
    def __init__(self, updates):
        self.updates = updates

    def update(self, payload):
        self.updates.append(payload)
        return _UpdateEq(payload)


class _SupabaseJobs:
    def __init__(self, jobs, retry_job=None):
        self.jobs = jobs
        self.retry_job = retry_job
        self.updates = []
        self.rpc_calls = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if name == "claim_evaluation_jobs":
            return _Exec(self.jobs)
        if name == "retry_evaluation_job":
            return _Exec(self.retry_job)
        raise AssertionError(name)

    def table(self, name):
        assert name == "evaluation_jobs"
        return _Table(self.updates)


def test_process_evaluation_jobs_marks_claimed_job_completed(monkeypatch):
    job = {
        "id": "job-1",
        "meet_id": "550e8400-e29b-41d4-a716-446655440000",
        "attempts": 0,
        "max_attempts": 5,
    }
    fake_supabase = _SupabaseJobs([job])

    async def _fake_evaluate(request):
        return AnalysisResponse(
            status="success",
            message=f"evaluated {request.meet_id}",
            timestamp="2026-04-29T00:00:00",
            execution_time="0:00:01",
            result={"compatibility_score": 80},
            evaluation_id="eval-1",
        )

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_client", lambda _url, _key: fake_supabase)
    monkeypatch.setattr(api_module, "evaluate_single_meet", _fake_evaluate)

    response = TestClient(app).post("/evaluation-jobs/process", json={"limit": 1, "worker_id": "worker-test"})

    assert response.status_code == 200
    body = response.json()
    assert body["claimed"] == 1
    assert body["processed"][0]["status"] == "completed"
    assert fake_supabase.updates[0]["status"] == "completed"
    assert fake_supabase.updates[0]["attempts"] == 1
    assert fake_supabase.updates[0]["result"]["evaluation_id"] == "eval-1"


def test_process_evaluation_jobs_marks_failed_job_retryable(monkeypatch):
    job = {
        "id": "job-2",
        "meet_id": "550e8400-e29b-41d4-a716-446655440001",
        "attempts": 1,
        "max_attempts": 5,
    }
    fake_supabase = _SupabaseJobs([job])

    async def _fake_evaluate(_request):
        raise RuntimeError("evaluation boom")

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_client", lambda _url, _key: fake_supabase)
    monkeypatch.setattr(api_module, "evaluate_single_meet", _fake_evaluate)

    response = TestClient(app).post("/evaluation-jobs/process", json={"limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["processed"][0]["status"] == "failed"
    assert body["processed"][0]["will_retry"] is True
    assert fake_supabase.updates[0]["status"] == "failed"
    assert fake_supabase.updates[0]["attempts"] == 2
    assert fake_supabase.updates[0]["last_error"] == "evaluation boom"


def test_retry_evaluation_job_queues_retry(monkeypatch):
    retry_job = {"id": "job-3", "status": "pending"}
    fake_supabase = _SupabaseJobs([], retry_job=retry_job)

    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(api_module, "create_client", lambda _url, _key: fake_supabase)

    response = TestClient(app).post("/evaluation-jobs/job-3/retry")

    assert response.status_code == 200
    assert response.json()["job"] == retry_job
    assert fake_supabase.rpc_calls[0] == ("retry_evaluation_job", {"p_job_id": "job-3"})
