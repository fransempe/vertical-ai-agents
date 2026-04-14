"""Smoke de composición de crews (sin ejecutar kickoff)."""

import json
from unittest.mock import patch

import pytest


def test_create_data_processing_crew_tasks_and_agents_count():
    pytest.importorskip("crewai")

    from crew import create_data_processing_crew

    crew = create_data_processing_crew()
    assert len(crew.tasks) == 7
    assert len(crew.agents) == 6


def test_create_data_processing_crew_sequential_and_verbose():
    pytest.importorskip("crewai")

    from crewai import Process

    from crew import create_data_processing_crew

    crew = create_data_processing_crew()
    assert crew.process == Process.sequential
    assert crew.verbose is True


def test_create_filtered_data_processing_crew_tasks_and_agents_count(monkeypatch):
    pytest.importorskip("crewai")

    import filtered_crew

    class _ToolStub:
        @staticmethod
        def func(jd_interview_id: str, limit: int = 100) -> str:
            return "{}"

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _ToolStub())

    jd = "550e8400-e29b-41d4-a716-446655440220"
    crew = filtered_crew.create_filtered_data_processing_crew(jd)
    assert len(crew.tasks) == 7
    assert len(crew.agents) == 6


def _jd_for_filtered():
    return "550e8400-e29b-41d4-a716-446655440220"


def test_filtered_crew_resolves_tool_via_wrapped(monkeypatch):
    pytest.importorskip("crewai")
    import filtered_crew

    calls = []

    def _inner(*args, **_kwargs):
        for a in args:
            if isinstance(a, str) and a.count("-") >= 4:
                calls.append(a)
                break
        return "{}"

    class _WithWrapped:
        __wrapped__ = _inner

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _WithWrapped())
    filtered_crew.create_filtered_data_processing_crew(_jd_for_filtered())
    assert calls == [_jd_for_filtered()]


def test_filtered_crew_resolves_tool_via_underscore_func(monkeypatch):
    pytest.importorskip("crewai")
    import filtered_crew

    calls = []

    def _inner(*args, **_kwargs):
        for a in args:
            if isinstance(a, str) and a.count("-") >= 4:
                calls.append(a)
                break
        return "{}"

    class _WithUsFunc:
        _func = _inner

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _WithUsFunc())
    filtered_crew.create_filtered_data_processing_crew(_jd_for_filtered())
    assert calls == [_jd_for_filtered()]


def test_filtered_crew_resolves_plain_callable_without_name(monkeypatch):
    pytest.importorskip("crewai")
    import filtered_crew

    calls = []

    def _bare(jd_id):
        calls.append(jd_id)
        return "{}"

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _bare)
    filtered_crew.create_filtered_data_processing_crew(_jd_for_filtered())
    assert calls == [_jd_for_filtered()]


def test_filtered_crew_probe_no_callable_shows_message(monkeypatch, capsys):
    pytest.importorskip("crewai")
    import filtered_crew

    class _NoWay:
        name = "stub_tool"

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _NoWay())
    filtered_crew.create_filtered_data_processing_crew(_jd_for_filtered())
    captured = capsys.readouterr()
    assert "No se pudo acceder" in captured.out or "No se pudo acceder" in captured.err


def test_filtered_crew_probe_call_raises_logs_traceback(monkeypatch, capsys):
    pytest.importorskip("crewai")
    import filtered_crew

    def _boom(jd_id):
        raise RuntimeError("probe fail")

    monkeypatch.setattr(filtered_crew, "get_conversations_by_jd_interview", _boom)
    crew = filtered_crew.create_filtered_data_processing_crew(_jd_for_filtered())
    assert len(crew.tasks) == 7
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "probe fail" in text or "Error al probar" in text


def test_create_candidate_matching_crew_composes(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import matching_crew

    crew = matching_crew.create_candidate_matching_crew()
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1


def test_create_candidate_matching_crew_with_user_and_client_ids(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import matching_crew

    crew = matching_crew.create_candidate_matching_crew(user_id="user-abc", client_id="client-xyz")
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1


def test_create_cv_analysis_crew_composes():
    pytest.importorskip("crewai")
    import cv_crew

    crew = cv_crew.create_cv_analysis_crew("folder/cv.pdf")
    assert len(crew.tasks) >= 1
    assert len(crew.agents) >= 1


def test_create_single_meet_evaluation_crew_composes(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    class _FakeMeetTool:
        @staticmethod
        def func(mid):
            return json.dumps({"conversation": {}, "jd_interview": {}})

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _FakeMeetTool())

    mid = "550e8400-e29b-41d4-a716-446655440000"
    crew = single_meet_crew.create_single_meet_evaluation_crew(mid)
    assert len(crew.agents) == 1
    assert len(crew.tasks) == 2


def _meet_id_smoke():
    return "550e8400-e29b-41d4-a716-446655440000"


def test_single_meet_crew_resolves_via_wrapped(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    calls = []

    def _inner(*args, **_kwargs):
        for a in args:
            if isinstance(a, str) and a.count("-") >= 4:
                calls.append(a)
                break
        return json.dumps({})

    class _W:
        __wrapped__ = _inner

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _W())
    single_meet_crew.create_single_meet_evaluation_crew(_meet_id_smoke())
    assert calls == [_meet_id_smoke()]


def test_single_meet_crew_resolves_via_underscore_func(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    calls = []

    def _inner(*args, **_kwargs):
        for a in args:
            if isinstance(a, str) and a.count("-") >= 4:
                calls.append(a)
                break
        return json.dumps({})

    class _F:
        _func = _inner

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _F())
    single_meet_crew.create_single_meet_evaluation_crew(_meet_id_smoke())
    assert calls == [_meet_id_smoke()]


def test_single_meet_crew_resolves_plain_callable(monkeypatch):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    calls = []

    def _bare(mid):
        calls.append(mid)
        return json.dumps({})

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _bare)
    single_meet_crew.create_single_meet_evaluation_crew(_meet_id_smoke())
    assert calls == [_meet_id_smoke()]


def test_single_meet_crew_probe_no_callable(monkeypatch, capsys):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    class _No:
        name = "meet_tool"

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _No())
    single_meet_crew.create_single_meet_evaluation_crew(_meet_id_smoke())
    out = capsys.readouterr().out
    assert "No se pudo acceder" in out


def test_single_meet_crew_probe_raises(monkeypatch, capsys):
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    import single_meet_crew

    def _boom(mid):
        raise RuntimeError("meet probe")

    monkeypatch.setattr(single_meet_crew, "get_meet_evaluation_data", _boom)
    crew = single_meet_crew.create_single_meet_evaluation_crew(_meet_id_smoke())
    assert len(crew.tasks) == 2
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "meet probe" in text or "Error al probar" in text


def test_matching_crew_kickoff_patched_on_crew_class(monkeypatch):
    """`unittest.mock.patch.object(Crew, kickoff)` evita LLM real (tanda 20)."""
    pytest.importorskip("crewai")
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    from crewai import Crew

    import matching_crew

    def _fake_kickoff(_self):
        return '{"matches": []}'

    with patch.object(Crew, "kickoff", _fake_kickoff):
        crew = matching_crew.create_candidate_matching_crew()
        out = crew.kickoff()
        assert "matches" in out


def test_cv_analysis_crew_kickoff_patched_on_crew_class():
    """`patch.object(Crew, kickoff)` en `cv_crew` sin LLM real (tanda 20)."""
    pytest.importorskip("crewai")
    from crewai import Crew

    import cv_crew

    def _fake_kickoff(_self):
        return '{"summary": "ok"}'

    with patch.object(Crew, "kickoff", _fake_kickoff):
        crew = cv_crew.create_cv_analysis_crew("folder/cv.pdf")
        out = crew.kickoff()
        assert "summary" in out
