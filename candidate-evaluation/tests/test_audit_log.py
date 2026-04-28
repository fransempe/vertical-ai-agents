from types import SimpleNamespace

import pytest

from utils import audit_log


class _FakeAuditTable:
    def __init__(self, client):
        self.client = client

    def insert(self, payload):
        self.client.inserted_payload = payload
        return self

    def execute(self):
        self.client.executed = True
        return SimpleNamespace(data=[{"id": "audit-1"}])


class _FakeAuditClient:
    def __init__(self):
        self.table_name = None
        self.inserted_payload = None
        self.executed = False

    def table(self, table_name):
        self.table_name = table_name
        return _FakeAuditTable(self)


def test_record_audit_event_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AUDIT_LOG_ENABLED", raising=False)

    assert audit_log.record_audit_event(action="candidate_evaluation_started", status="started") is False


def test_record_audit_event_inserts_sanitized_payload(monkeypatch):
    fake_client = _FakeAuditClient()

    import tools.vector_tools as vector_tools

    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    monkeypatch.setattr(vector_tools, "get_supabase_client", lambda: fake_client)

    recorded = audit_log.record_audit_event(
        action="candidate_evaluation_completed",
        status="success",
        resource_type="meet",
        resource_id="meet-1",
        metadata={
            "score": 82,
            "nested": {"api_key": "secret-value", "safe": "visible"},
            "items": [{"token": "hidden"}],
        },
    )

    assert recorded is True
    assert fake_client.table_name == audit_log.AUDIT_TABLE_NAME
    assert fake_client.executed is True
    assert fake_client.inserted_payload["action"] == "candidate_evaluation_completed"
    assert fake_client.inserted_payload["resource_type"] == "meet"
    assert fake_client.inserted_payload["resource_id"] == "meet-1"
    assert fake_client.inserted_payload["metadata"]["score"] == 82
    assert fake_client.inserted_payload["metadata"]["nested"]["api_key"] == "***"
    assert fake_client.inserted_payload["metadata"]["nested"]["safe"] == "visible"
    assert fake_client.inserted_payload["metadata"]["items"][0]["token"] == "***"


def test_record_audit_event_returns_false_if_insert_fails(monkeypatch):
    import tools.vector_tools as vector_tools

    monkeypatch.setenv("AUDIT_LOG_ENABLED", "true")
    monkeypatch.setattr(
        vector_tools,
        "get_supabase_client",
        lambda: (_ for _ in ()).throw(RuntimeError("supabase down")),
    )

    assert audit_log.record_audit_event(action="candidate_evaluation_failed", status="failed") is False


def test_record_audit_event_validates_required_fields():
    with pytest.raises(ValueError, match="action is required"):
        audit_log.record_audit_event(action="", status="success")

    with pytest.raises(ValueError, match="status is required"):
        audit_log.record_audit_event(action="candidate_evaluation_completed", status="")


def test_record_evaluation_audit_event_maps_failed_events(monkeypatch):
    captured = {}

    def _fake_record_audit_event(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(audit_log, "record_audit_event", _fake_record_audit_event)

    assert (
        audit_log.record_evaluation_audit_event(
            meet_id="meet-1",
            action="candidate_evaluation",
            status="failed",
            metadata={"step": "crew"},
            error_message="boom",
        )
        is True
    )
    assert captured["actor_type"] == "system"
    assert captured["actor_id"] == "automatic-evaluation"
    assert captured["source"] == "candidate-evaluation-api"
    assert captured["event_type"] == "error"
    assert captured["severity"] == "error"
    assert captured["resource_type"] == "meet"
    assert captured["resource_id"] == "meet-1"
    assert captured["error_message"] == "boom"


def test_record_elevenlabs_agent_audit_event_maps_failed_events(monkeypatch):
    captured = {}

    def _fake_record_audit_event(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(audit_log, "record_audit_event", _fake_record_audit_event)

    assert (
        audit_log.record_elevenlabs_agent_audit_event(
            jd_interview_id="jd-1",
            action="elevenlabs_agent_creation",
            status="failed",
            metadata={"step": "create_agent"},
            error_message="boom",
        )
        is True
    )
    assert captured["actor_type"] == "system"
    assert captured["actor_id"] == "elevenlabs-agent-creator"
    assert captured["source"] == "candidate-evaluation-api"
    assert captured["event_type"] == "error"
    assert captured["severity"] == "error"
    assert captured["resource_type"] == "jd_interview"
    assert captured["resource_id"] == "jd-1"
    assert captured["error_message"] == "boom"


def test_record_matching_audit_event_maps_failed_events(monkeypatch):
    captured = {}

    def _fake_record_audit_event(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(audit_log, "record_audit_event", _fake_record_audit_event)

    assert (
        audit_log.record_matching_audit_event(
            run_id="run-1",
            action="candidate_matching",
            status="failed",
            metadata={"step": "deterministic_matching"},
            error_message="boom",
        )
        is True
    )
    assert captured["actor_type"] == "system"
    assert captured["actor_id"] == "matching-engine"
    assert captured["source"] == "candidate-evaluation-api"
    assert captured["event_type"] == "error"
    assert captured["severity"] == "error"
    assert captured["resource_type"] == "matching_run"
    assert captured["resource_id"] == "run-1"
    assert captured["error_message"] == "boom"


def test_record_cv_candidate_audit_event_maps_failed_events(monkeypatch):
    captured = {}

    def _fake_record_audit_event(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(audit_log, "record_audit_event", _fake_record_audit_event)

    assert (
        audit_log.record_cv_candidate_audit_event(
            filename="folder/cv.pdf",
            action="candidate_creation_from_cv",
            status="failed",
            metadata={"candidate_status": "failed"},
            error_message="boom",
        )
        is True
    )
    assert captured["actor_type"] == "system"
    assert captured["actor_id"] == "cv-analysis"
    assert captured["source"] == "candidate-evaluation-api"
    assert captured["event_type"] == "error"
    assert captured["severity"] == "error"
    assert captured["resource_type"] == "cv"
    assert captured["resource_id"] == "folder/cv.pdf"
    assert captured["error_message"] == "boom"
