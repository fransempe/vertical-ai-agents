"""Tests unitarios de `tools.elevenlabs_tools` (prompt desde JD, API ElevenLabs)."""

import json

import pytest

pytest.importorskip("crewai")


def _patch_prompt_crew(monkeypatch, kickoff_result):
    from tools import elevenlabs_tools

    class _FakeCrew:
        def kickoff(self):
            return kickoff_result

    monkeypatch.setattr(elevenlabs_tools, "create_elevenlabs_prompt_generator_agent", lambda: object())
    monkeypatch.setattr(
        elevenlabs_tools,
        "create_elevenlabs_prompt_generation_task",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(elevenlabs_tools, "Crew", lambda **kw: _FakeCrew())


def test_generate_elevenlabs_prompt_from_jd_parses_json(monkeypatch):
    from tools import elevenlabs_tools

    payload = {
        "prompt": "Prompt generado",
        "cliente": {"nombre": "ACME", "responsable": "R", "email": "c@acme.com", "telefono": "1"},
        "agent_name": "Agente JD",
    }
    _patch_prompt_crew(monkeypatch, json.dumps(payload))

    out = elevenlabs_tools.generate_elevenlabs_prompt_from_jd("Entrevista X", "JD body", "fallback@x.com")
    assert out["prompt"] == "Prompt generado"
    assert out["agent_name"] == "Agente JD"
    assert out["cliente"]["nombre"] == "ACME"
    assert out["cliente"]["email"] == "c@acme.com"


def test_generate_elevenlabs_prompt_from_jd_json_decode_error_uses_strip_fallback(monkeypatch):
    from tools import elevenlabs_tools

    # Empieza con "{" para tomar json_match directo; JSON inválido → except interno (82–89).
    _patch_prompt_crew(monkeypatch, '{"prompt": ')

    out = elevenlabs_tools.generate_elevenlabs_prompt_from_jd("Busq2", "JD2", "s2@mail.com")
    assert out["prompt"].startswith('{"prompt":')
    assert out["cliente"]["email"] == "s2@mail.com"


def test_generate_elevenlabs_prompt_from_jd_fallback_when_not_json(monkeypatch):
    from tools import elevenlabs_tools

    _patch_prompt_crew(monkeypatch, "texto plano sin llaves json")

    out = elevenlabs_tools.generate_elevenlabs_prompt_from_jd("Busq", "Descripción larga", "s@mail.com")
    assert "Busq" in out["prompt"]
    assert "Descripción larga" in out["prompt"]
    assert out["cliente"]["email"] == "s@mail.com"
    assert out["agent_name"] == "Busq"


def test_generate_elevenlabs_prompt_from_jd_outer_exception_returns_default(monkeypatch):
    from tools import elevenlabs_tools

    def _boom():
        raise RuntimeError("crew fail")

    monkeypatch.setattr(elevenlabs_tools, "create_elevenlabs_prompt_generator_agent", _boom)

    out = elevenlabs_tools.generate_elevenlabs_prompt_from_jd("E1", "JD1", "e@e.com")
    assert "E1" in out["prompt"]
    assert "JD1" in out["prompt"]
    assert out["cliente"]["email"] == "e@e.com"


def test_create_elevenlabs_agent_returns_none_without_api_key(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert elevenlabs_tools.create_elevenlabs_agent("A", "I", "J", "s@x.com") is None


def test_update_elevenlabs_agent_prompt_returns_none_without_api_key(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert elevenlabs_tools.update_elevenlabs_agent_prompt("ag_1", "nuevo prompt") is None


def test_update_elevenlabs_agent_prompt_success_mocked(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test-key")

    class _Resp:
        def dict(self):
            return {"agent_id": "ag_1", "updated": True}

    class _Agents:
        def update(self, **_kwargs):
            return _Resp()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())

    out = elevenlabs_tools.update_elevenlabs_agent_prompt("ag_1", "prompt completo")
    assert out is not None
    assert out.get("updated") is True


def test_create_elevenlabs_agent_success_mocked(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")

    def _fake_prompt(*_a, **_k):
        return {
            "prompt": "Prompt base",
            "cliente": {"nombre": "", "responsable": "", "email": "c@x.com", "telefono": ""},
            "agent_name": "Agente Entrevista",
        }

    captured = {}

    class _CreateResp:
        def dict(self):
            return {"agent_id": "new_ag_1", "name": "Agente Entrevista"}

    class _Agents:
        def create(self, **kwargs):
            captured["conversation_config"] = kwargs["conversation_config"]
            return _CreateResp()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    out = elevenlabs_tools.create_elevenlabs_agent(
        "Agente Entrevista",
        "Int",
        "JD",
        "c@x.com",
    )
    assert out is not None
    assert out.get("agent_id") == "new_ag_1"
    assert out.get("cliente_data") is not None
    captured_prompt = captured["conversation_config"]["agent"]["prompt"]["prompt"]
    english_preset = captured["conversation_config"]["language_presets"]["en"]["overrides"]["agent"]
    assert "What is your current role and what are your main responsibilities?" in captured_prompt
    assert "Can you describe a challenging project you worked on and how you handled it?" in captured_prompt
    assert "EXACTAMENTE 3 preguntas" in captured_prompt
    assert "Now we'll switch to English" in english_preset["first_message"]
    assert "What is your current role and what are your main responsibilities?" in english_preset["prompt"]["prompt"]
    assert (
        "Can you describe a challenging project you worked on and how you handled it?"
        in english_preset["prompt"]["prompt"]
    )
    assert "Randomly choose EXACTLY 3 questions" in english_preset["prompt"]["prompt"]


def test_create_elevenlabs_agent_uses_voice_id_from_env(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice_from_env")

    def _fake_prompt(*_a, **_k):
        return {"prompt": "P", "cliente": {}, "agent_name": "A"}

    captured = {}

    class _CreateResp:
        def dict(self):
            return {"agent_id": "ag"}

    class _Agents:
        def create(self, **kwargs):
            captured["tts"] = kwargs["conversation_config"]["tts"]
            return _CreateResp()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    elevenlabs_tools.create_elevenlabs_agent("A", "I", "J", "e@e.com")

    assert captured["tts"]["voice_id"] == "voice_from_env"


def test_create_elevenlabs_agent_ignores_generated_name_with_null(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")

    def _fake_prompt(*_a, **_k):
        return {
            "prompt": "P",
            "cliente": {},
            "agent_name": "null - Búsqueda 1",
        }

    captured = {}

    class _CreateResp:
        def dict(self):
            return {"agent_id": "ag"}

    class _Agents:
        def create(self, **kwargs):
            captured["name"] = kwargs.get("name")
            return _CreateResp()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    elevenlabs_tools.create_elevenlabs_agent("Fallback Name", "I", "J", "e@e.com")
    assert captured.get("name") == "Fallback Name"


def test_create_elevenlabs_agent_prepends_client_name(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")

    def _fake_prompt(*_a, **_k):
        return {
            "prompt": "P",
            "cliente": {"nombre": "ClienteX", "email": "c@c.com"},
            "agent_name": "Entrevistador",
        }

    captured = {}

    class _CreateResp:
        def dict(self):
            return {}

    class _Agents:
        def create(self, **kwargs):
            captured["name"] = kwargs.get("name")
            return _CreateResp()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    elevenlabs_tools.create_elevenlabs_agent("Entrevistador", "I", "J", "e@e.com")
    assert captured.get("name") == "ClienteX - Entrevistador"


def test_create_elevenlabs_agent_returns_none_when_create_raises(monkeypatch):
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")

    def _fake_prompt(*_a, **_k):
        return {"prompt": "P", "cliente": {}, "agent_name": "A"}

    class _Agents:
        def create(self, **_kwargs):
            raise RuntimeError("API rate limit")

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    assert elevenlabs_tools.create_elevenlabs_agent("A", "I", "J", "e@e.com") is None


def test_create_elevenlabs_agent_opaque_response_without_dict(monkeypatch):
    """Respuesta sin .dict() ni __dict__ (p. ej. __slots__): rama else con str(response)."""
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-eleven-test")
    monkeypatch.setenv("ELEVENLABS_TOOL_ID", "tool_xyz")

    def _fake_prompt(*_a, **_k):
        return {"prompt": "P", "cliente": {}, "agent_name": "A"}

    class _Opaque:
        __slots__ = ()

        def __str__(self):
            return "agent_opaque_id"

    class _Agents:
        def create(self, **_kwargs):
            return _Opaque()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())
    monkeypatch.setattr(elevenlabs_tools, "generate_elevenlabs_prompt_from_jd", _fake_prompt)

    out = elevenlabs_tools.create_elevenlabs_agent("A", "I", "J", "e@e.com")
    assert out is not None
    assert out.get("agent_id") == "agent_opaque_id"
    assert out.get("cliente_data") == {}


def test_update_elevenlabs_agent_prompt_opaque_response_without_dict(monkeypatch):
    """Misma rama que create: sin .dict() ni __dict__ → result + agent_id."""
    from tools import elevenlabs_tools

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-test-key")

    class _Opaque:
        __slots__ = ()

        def __str__(self):
            return "patch_ok"

    class _Agents:
        def update(self, **_kwargs):
            return _Opaque()

    class _Conv:
        agents = _Agents()

    class _FakeElevenLabs:
        conversational_ai = _Conv()

    monkeypatch.setattr(elevenlabs_tools, "ElevenLabs", lambda **kw: _FakeElevenLabs())

    out = elevenlabs_tools.update_elevenlabs_agent_prompt("ag_42", "nuevo")
    assert out is not None
    assert out.get("agent_id") == "ag_42"
    assert out.get("result") == "patch_ok"
