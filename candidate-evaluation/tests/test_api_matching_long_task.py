"""`do_matching_long_task` usa motor determinístico; mocks sobre `run_deterministic_matching`."""

import pytest

pytest.importorskip("boto3")

import api as api_module
from api import matching_runs


def test_do_matching_long_task_error_when_env_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    rid = "run-env-miss-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "error"
        err = matching_runs[rid]["error"]
        assert "faltantes" in err or "Variables" in err
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_success_with_user_and_client_filters(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    monkeypatch.setattr(
        api_module,
        "run_deterministic_matching",
        lambda **kw: [{"candidate": {"id": "c1"}, "matching_interviews": [{"x": 1}]}],
    )
    rid = "run-ok-filter-t16"
    try:
        api_module.do_matching_long_task(rid, "user-1", "client-1")
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_success_without_filters(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    monkeypatch.setattr(api_module, "run_deterministic_matching", lambda **kw: [])
    rid = "run-ok-nofilter-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_only_user_id_uses_unfiltered_branch(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    monkeypatch.setattr(api_module, "run_deterministic_matching", lambda **kw: [])
    rid = "run-user-only-t16"
    try:
        api_module.do_matching_long_task(rid, "user-only", None)
        assert matching_runs[rid]["status"] == "done"
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_deterministic_raises_sets_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    def _boom(**kw):
        raise RuntimeError("matching engine boom")

    monkeypatch.setattr(api_module, "run_deterministic_matching", _boom)
    rid = "run-err-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "error"
        assert "matching engine boom" in matching_runs[rid]["error"]
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_two_candidate_groups(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")

    two = [
        {"candidate": {"id": "a"}, "matching_interviews": []},
        {"candidate": {"id": "b"}, "matching_interviews": []},
    ]
    monkeypatch.setattr(api_module, "run_deterministic_matching", lambda **kw: two)
    rid = "run-two-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 2
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_logs_matching_inputs_called(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    called = []

    def _log(**kw):
        called.append(kw)

    monkeypatch.setattr(api_module, "log_matching_inputs_debug", _log)
    monkeypatch.setattr(api_module, "run_deterministic_matching", lambda **kw: [])
    rid = "run-log-t16"
    try:
        api_module.do_matching_long_task(rid, "u1", "c1")
        assert called == [{"user_id": "u1", "client_id": "c1"}]
    finally:
        matching_runs.pop(rid, None)
