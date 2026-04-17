"""Tests unitarios del motor determinístico de matching."""

from matching_engine import (
    _jd_requirement_tokens,
    _score_from_overlap,
    to_canonical,
)


def test_to_canonical_aliases():
    assert to_canonical("ReactJS") == "react"
    assert to_canonical("JS") == "javascript"
    assert to_canonical("node.js") == "nodejs"


def test_jd_tokens_from_stack_and_description():
    ts = "React, TypeScript, Node.js"
    desc = "We also use Docker and AWS for deployment."
    s = _jd_requirement_tokens(ts, desc)
    assert "react" in s
    assert "typescript" in s
    assert "nodejs" in s
    assert "docker" in s
    assert "aws" in s


def test_score_from_overlap():
    assert _score_from_overlap({"react"}, {"react", "vue"}) >= 30
    assert _score_from_overlap(set(), {"react"}) == 0
