"""Smoke de `main.main()` sin ejecutar el crew real."""

import json

import pytest


def test_main_returns_none_when_env_vars_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import main as main_module

    assert main_module.main() is None


def test_main_success_writes_json_and_returns_kickoff_result(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import main as main_module

    class _FakeCrew:
        def kickoff(self):
            return json.dumps({"status": "ok", "n": 1})

    monkeypatch.setattr(main_module, "create_data_processing_crew", lambda: _FakeCrew())

    result = main_module.main()
    assert json.loads(result)["status"] == "ok"
    written = list(tmp_path.glob("conversation_results_*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["n"] == 1


def test_main_saves_txt_when_kickoff_not_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import main as main_module

    class _FakeCrew:
        def kickoff(self):
            return "not json {"

    monkeypatch.setattr(main_module, "create_data_processing_crew", lambda: _FakeCrew())

    main_module.main()
    written = list(tmp_path.glob("conversation_results_*.txt"))
    assert len(written) == 1
    assert "not json" in written[0].read_text(encoding="utf-8")


def test_main_keyboard_interrupt_logs(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import main as main_module

    class _FakeCrew:
        def kickoff(self):
            raise KeyboardInterrupt()

    monkeypatch.setattr(main_module, "create_data_processing_crew", lambda: _FakeCrew())

    assert main_module.main() is None
    assert "interrumpido" in capsys.readouterr().out.lower()


def test_main_propagates_unexpected_exception(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    import main as main_module

    class _FakeCrew:
        def kickoff(self):
            raise RuntimeError("kickoff boom")

    monkeypatch.setattr(main_module, "create_data_processing_crew", lambda: _FakeCrew())

    with pytest.raises(RuntimeError, match="kickoff boom"):
        main_module.main()
