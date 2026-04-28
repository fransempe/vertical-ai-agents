"""
Supabase-backed audit events for business and system movements.

The audit writer is intentionally non-blocking for product flows: database
failures are logged locally and do not raise back to API handlers.
"""

import os
from typing import Any

from utils.logger import evaluation_logger

AUDIT_TABLE_NAME = "audit_events"
SYSTEM_ACTOR_ID = "candidate-evaluation-service"

_ENABLED_VALUES = {"1", "true", "yes", "on"}
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "token",
)


def is_audit_log_enabled() -> bool:
    """Return whether audit writes should be attempted."""
    return os.getenv("AUDIT_LOG_ENABLED", "").strip().lower() in _ENABLED_VALUES


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, nested_value in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_value(nested_value)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    return value


def record_audit_event(
    *,
    action: str,
    status: str,
    actor_type: str = "system",
    actor_id: str | None = SYSTEM_ACTOR_ID,
    source: str = "candidate-evaluation",
    event_type: str = "audit",
    severity: str = "info",
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
    error_stack: str | None = None,
) -> bool:
    """
    Insert one append-only audit event in Supabase.

    Returns True if the insert was attempted and completed, False if audit is
    disabled or the insert failed.
    """
    if not action:
        raise ValueError("action is required")
    if not status:
        raise ValueError("status is required")

    if not is_audit_log_enabled():
        return False

    payload = {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "source": source,
        "event_type": event_type,
        "severity": severity,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "status": status,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "before_state": _sanitize_value(before_state) if before_state else None,
        "after_state": _sanitize_value(after_state) if after_state else None,
        "metadata": _sanitize_value(metadata or {}),
        "error_message": error_message,
        "error_stack": error_stack,
    }

    try:
        from tools.vector_tools import get_supabase_client

        get_supabase_client().table(AUDIT_TABLE_NAME).insert(payload).execute()
        return True
    except Exception as audit_error:
        evaluation_logger.log_error("Audit Log", f"No se pudo registrar evento de auditoria: {audit_error}")
        return False


def record_evaluation_audit_event(
    *,
    meet_id: str,
    action: str,
    status: str,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """Record an audit event emitted by the automatic meet evaluation flow."""
    return record_audit_event(
        action=action,
        status=status,
        actor_type="system",
        actor_id="automatic-evaluation",
        source="candidate-evaluation-api",
        event_type="error" if status == "failed" else "audit",
        severity="error" if status == "failed" else "info",
        resource_type="meet",
        resource_id=meet_id,
        metadata=metadata,
        error_message=error_message,
    )


def record_elevenlabs_agent_audit_event(
    *,
    jd_interview_id: str,
    action: str,
    status: str,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """Record an audit event emitted by the ElevenLabs agent creation flow."""
    return record_audit_event(
        action=action,
        status=status,
        actor_type="system",
        actor_id="elevenlabs-agent-creator",
        source="candidate-evaluation-api",
        event_type="error" if status == "failed" else "audit",
        severity="error" if status == "failed" else "info",
        resource_type="jd_interview",
        resource_id=jd_interview_id,
        metadata=metadata,
        error_message=error_message,
    )


def record_matching_audit_event(
    *,
    run_id: str,
    action: str,
    status: str,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """Record an audit event emitted by the candidate matching flow."""
    return record_audit_event(
        action=action,
        status=status,
        actor_type="system",
        actor_id="matching-engine",
        source="candidate-evaluation-api",
        event_type="error" if status == "failed" else "audit",
        severity="error" if status == "failed" else "info",
        resource_type="matching_run",
        resource_id=run_id,
        metadata=metadata,
        error_message=error_message,
    )


def record_cv_candidate_audit_event(
    *,
    filename: str,
    action: str,
    status: str,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> bool:
    """Record an audit event emitted by candidate creation from CV analysis."""
    return record_audit_event(
        action=action,
        status=status,
        actor_type="system",
        actor_id="cv-analysis",
        source="candidate-evaluation-api",
        event_type="error" if status == "failed" else "audit",
        severity="error" if status == "failed" else "info",
        resource_type="cv",
        resource_id=filename,
        metadata=metadata,
        error_message=error_message,
    )
