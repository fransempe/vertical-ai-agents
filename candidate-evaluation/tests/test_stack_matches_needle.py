"""Tests directos de `_stack_matches_needle_token` (etiquetas con `.`, `#`, `/`, SQL)."""

import pytest

pytest.importorskip("boto3")


def test_java_not_in_javascript_token():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["javascript"], "java") is False
    assert _stack_matches_needle_token(["java"], "java") is True


def test_exact_csharp_and_dotnet():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["c#"], "c#") is True
    assert _stack_matches_needle_token([".net"], ".net") is True


def test_next_js_token():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["next.js"], "next.js") is True


def test_ci_cd_slash_needle():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["ci/cd"], "ci/cd") is True


def test_sql_postgresql_suffix():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["postgresql"], "sql") is True
    assert _stack_matches_needle_token(["mysql"], "sql") is True
    assert _stack_matches_needle_token(["redis"], "sql") is False


def test_robot_framework_multiword():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["robot framework"], "robot framework") is True


def test_node_js_needle_not_javascript():
    from tools.cv_tools import _stack_matches_needle_token

    assert _stack_matches_needle_token(["javascript"], "node.js") is False
    assert _stack_matches_needle_token(["node.js"], "node.js") is True
