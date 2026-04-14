"""Helpers y modelos de api.py (requiere dependencias de runtime, p. ej. boto3)."""

import base64
import builtins

import pytest

pytest.importorskip("boto3")

import api as api_module  # noqa: E402
from api import (  # noqa: E402
    AnalysisResponse,
    CVRequest,
    MatchingRequest,
    SingleMeetRequest,
    b64decode,
    format_soft_skills,
    format_technical_questions,
    load_email_template,
    render_email_template,
)


def test_format_soft_skills_empty():
    assert format_soft_skills({}) == "No disponible"
    assert format_soft_skills(None) == "No disponible"  # type: ignore[arg-type]


def test_format_soft_skills_with_values():
    text = format_soft_skills(
        {
            "communication": "Buena",
            "leadership": 8,
            "unknown_key": "x",
        }
    )
    assert "Comunicación" in text
    assert "Liderazgo" in text
    assert "8/10" in text
    assert "Unknown Key" in text


def test_format_technical_questions():
    assert format_technical_questions([]) == "No disponible"
    out = format_technical_questions(
        [
            {"question": "Q1?", "answered": "Sí"},
            {"question": "Q2?"},
        ]
    )
    assert "Q1?" in out
    assert "Contestada" in out


def test_b64decode_padding():
    raw = base64.b64encode(b"hola").decode().rstrip("=")
    assert b64decode(raw) == "hola"


def test_b64decode_invalid_utf8_replaced():
    raw = base64.b64encode(b"\xff\xfe").decode()
    out = b64decode(raw)
    assert "\ufffd" in out


def test_render_email_template_empty_when_missing_file(monkeypatch):
    monkeypatch.setattr(api_module, "load_email_template", lambda name: "")
    assert render_email_template("missing.html", x=1) == ""


def test_render_email_template_keyerror_returns_raw_template(monkeypatch):
    monkeypatch.setattr(api_module, "load_email_template", lambda name: "Hola {solo_esta}")
    out = render_email_template("t.html", otro=1)
    assert out == "Hola {solo_esta}"


def test_render_email_template_format_error_returns_template(monkeypatch):
    monkeypatch.setattr(api_module, "load_email_template", lambda name: "{mal")
    out = render_email_template("t.html")
    assert "{mal" in out


def test_load_email_template_missing():
    assert load_email_template("no_existe_xyz.html") == ""


def test_load_email_template_read_error_returns_empty(monkeypatch):
    """Rama except Exception en load_email_template (no solo FileNotFoundError)."""

    def _raise(*_a, **_k):
        raise PermissionError("denied")

    monkeypatch.setattr(builtins, "open", _raise)
    assert load_email_template("evaluation_match.html") == ""


def test_load_and_render_evaluation_match_template():
    tpl = load_email_template("evaluation_match.html")
    assert tpl
    kwargs = {
        "interview_name": "Dev",
        "compatibility_score": "80",
        "final_recommendation": "Go",
        "candidate_name": "Ana",
        "candidate_email": "a@a.com",
        "candidate_phone": "1",
        "candidate_tech_stack": "Py",
        "candidate_cv_url": "http://x",
        "soft_skills_formatted": "—",
        "emotion_prosody_summary_text": "—",
        "emotion_burst_summary_text": "—",
        "knowledge_level": "Medio",
        "practical_experience": "2y",
        "technical_questions_formatted": "—",
        "justification": "Porque sí",
        "conversation_text": "(vacío)",
        "client_name": "ACME",
        "client_responsible": "Bob",
        "client_phone": "2",
        "client_email": "c@c.com",
        "meet_id": "m1",
        "jd_interviews_id": "j1",
    }
    html = render_email_template("evaluation_match.html", **kwargs)
    assert "Ana" in html
    assert "ACME" in html


def test_pydantic_models_defaults():
    assert SingleMeetRequest(meet_id="550e8400-e29b-41d4-a716-446655440000").meet_id
    assert CVRequest(filename="f.pdf").filename
    assert MatchingRequest().user_id is None
    r = AnalysisResponse(
        status="ok",
        message="m",
        timestamp="t",
    )
    assert r.status == "ok"
