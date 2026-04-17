"""`do_matching_long_task` (matching en background) con mocks; no HTTP."""

import json
import re

import pytest

pytest.importorskip("boto3")

import api as api_module
from api import matching_runs


def test_do_matching_long_task_error_when_env_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return json.dumps({"matches": [{"id": "m1"}]})

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
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
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return json.dumps({"matches": []})

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-ok-nofilter-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_only_user_id_uses_unfiltered_branch(monkeypatch):
    """`user_id` sin `client_id` → rama sin filtros (335)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return json.dumps({"matches": []})

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-user-only-t16"
    try:
        api_module.do_matching_long_task(rid, "user-only", None)
        assert matching_runs[rid]["status"] == "done"
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_kickoff_raises_sets_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _BadCrew:
        def kickoff(self):
            raise RuntimeError("crew boom")

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _BadCrew())
    rid = "run-err-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "error"
        assert "crew boom" in matching_runs[rid]["error"]
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_result_as_json_list(monkeypatch):
    """`json.loads` devuelve lista → matches extraídos como lista (463–466)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return '[{"x": 1}, {"x": 2}]'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-list-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 2
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_dict_without_matches_key(monkeypatch):
    """Dict JSON sin clave `matches` → formato no reconocido; lista vacía (467–470)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return '{"foo": 1}'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-no-matches-key-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_uses_raw_attribute(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            class _R:
                raw = json.dumps({"matches": [{"id": "r1"}]})

            return _R()

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-raw-t16"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_extracts_matches_from_markdown_json_block(monkeypatch):
    """Estrategia 1: JSON dentro de ```json ... ``` (397–405)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            # Sin objetos anidados con `}` antes del cierre: el regex no-greedy del bloque markdown
            # captura hasta el primer `}` tras "matches".
            return """Análisis del modelo:
```json
{"matches": ["md1"]}
```
fin"""

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-md-json-t17"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_markdown_block_inner_json_invalid_then_brace_path(monkeypatch):
    """Bloque ```json``` con JSON inválido (404–405); luego texto con JSON válido con `"matches"`."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return """Modelo:
```json
{"matches": [1,2,], "x": 1}
```
extra
{"matches": ["recovered"]}
"""

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-md-invalid-t19"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_balanced_brace_skips_when_no_open_brace_before_matches(monkeypatch):
    """Estrategia 2: posición `"matches"` sin `{` previo → `continue` (415)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return 'noise "matches" tail {"matches": [{"id": "ok"}]}'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-brace-no-open-t21"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_strategy_3_json_decode_error_when_brace_slice_invalid(monkeypatch):
    """Estrategia 3: slice con `\"matches\"` pero JSON inválido → except (448–449)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return 'garbage {"matches": [1,2,]}'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-strat3-decode-err-t21"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_strategy_3_first_to_last_brace_when_finditer_empty(monkeypatch):
    """Estrategia 3 (438–449): si `finditer('"matches"')` no devuelve posiciones, primer `{`…último `}`."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    orig_finditer = re.finditer

    def _finditer_no_matches_key(pattern, string, *args, **kwargs):
        if pattern == r'"matches"':
            return iter([])
        return orig_finditer(pattern, string, *args, **kwargs)

    monkeypatch.setattr(re, "finditer", _finditer_no_matches_key)

    class _FakeCrew:
        def kickoff(self):
            return 'prefijo no-json {"matches": [1]} sufijo'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-strat3-t20"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_extracts_matches_via_balanced_braces(monkeypatch):
    """Estrategia 2: texto no JSON con objeto `"matches"` balanceado (407–436)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return 'Ruido previo {"matches": [{"id": "brace1"}]} sufijo'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-brace-t17"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 1
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_unparseable_no_matches_literal_empty_total(monkeypatch):
    """Texto sin `\"matches\"` JSON ni JSON válido → 0 matches (rama 469–474)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return "solo texto sin comillas matches con formato json"

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-raw-no-matches-t20"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)


def test_do_matching_long_task_valid_json_dict_without_matches_key(monkeypatch):
    """Dict JSON sin clave `matches` → rama «formato no reconocido» (467–468)."""
    monkeypatch.setenv("SUPABASE_URL", "http://local.test")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _FakeCrew:
        def kickoff(self):
            return '{"foo": 1, "bar": 2}'

    monkeypatch.setattr(api_module, "create_candidate_matching_crew", lambda **kw: _FakeCrew())
    rid = "run-no-matches-dict-t18"
    try:
        api_module.do_matching_long_task(rid, None, None)
        assert matching_runs[rid]["status"] == "done"
        assert matching_runs[rid]["result"]["total_matches"] == 0
    finally:
        matching_runs.pop(rid, None)
