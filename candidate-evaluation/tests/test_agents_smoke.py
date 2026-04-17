"""Smoke mínimo de factories en agents.py (importa CrewAI / LangChain)."""

import pytest


def test_create_data_extractor_agent_role():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_data_extractor_agent

    agent = create_data_extractor_agent()
    assert agent.role == "Data Extraction Specialist"


def test_create_candidate_matching_agent_recruiter_tools_when_user_and_client():
    """266: con `user_id` y `client_id` se usa `get_candidates_by_recruiter`."""
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_candidate_matching_agent
    from tools.supabase_tools import get_candidates_by_recruiter, get_candidates_data

    uid = "550e8400-e29b-41d4-a716-446655440150"
    cid = "550e8400-e29b-41d4-a716-446655440151"

    agent_rec = create_candidate_matching_agent(user_id=uid, client_id=cid)
    assert get_candidates_by_recruiter in agent_rec.tools
    assert get_candidates_data not in agent_rec.tools

    agent_all = create_candidate_matching_agent()
    assert get_candidates_data in agent_all.tools


def test_create_elevenlabs_prompt_generator_agent_role():
    """319+: factory ElevenLabs prompt."""
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_elevenlabs_prompt_generator_agent

    agent = create_elevenlabs_prompt_generator_agent()
    assert "ElevenLabs" in agent.role
