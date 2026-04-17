"""Smoke de factories de tasks.py (CrewAI Task)."""

import pytest


def test_create_extraction_task_uses_agent():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_data_extractor_agent
    from tasks import create_extraction_task

    agent = create_data_extractor_agent()
    task = create_extraction_task(agent)
    assert task.agent is agent
    assert "conversaciones" in task.description.lower() or "supabase" in task.description.lower()


def test_create_analysis_task_has_extraction_context():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_conversation_analyzer_agent, create_data_extractor_agent
    from tasks import create_analysis_task, create_extraction_task

    ext_agent = create_data_extractor_agent()
    ana_agent = create_conversation_analyzer_agent()
    ext_task = create_extraction_task(ext_agent)
    ana_task = create_analysis_task(ana_agent, ext_task)
    assert ana_task.agent is ana_agent
    assert ext_task in ana_task.context


def test_create_job_analysis_task_has_extraction_context():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_data_extractor_agent, create_job_description_analyzer_agent
    from tasks import create_extraction_task, create_job_analysis_task

    ext_agent = create_data_extractor_agent()
    job_agent = create_job_description_analyzer_agent()
    ext_task = create_extraction_task(ext_agent)
    job_task = create_job_analysis_task(job_agent, ext_task)
    assert job_task.agent is job_agent
    assert ext_task in job_task.context
    assert "jd_interviews" in job_task.description.lower() or "descripciones" in job_task.description.lower()


def test_create_candidate_job_comparison_task_context():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import (
        create_candidate_matching_agent,
        create_conversation_analyzer_agent,
        create_data_extractor_agent,
        create_job_description_analyzer_agent,
    )
    from tasks import (
        create_analysis_task,
        create_candidate_job_comparison_task,
        create_extraction_task,
        create_job_analysis_task,
    )

    ext_agent = create_data_extractor_agent()
    ana_agent = create_conversation_analyzer_agent()
    job_agent = create_job_description_analyzer_agent()
    match_agent = create_candidate_matching_agent()

    ext_task = create_extraction_task(ext_agent)
    ana_task = create_analysis_task(ana_agent, ext_task)
    job_task = create_job_analysis_task(job_agent, ext_task)
    comp_task = create_candidate_job_comparison_task(match_agent, ext_task, ana_task, job_task)

    assert comp_task.agent is match_agent
    assert ext_task in comp_task.context
    assert ana_task in comp_task.context
    assert job_task in comp_task.context
    assert len(comp_task.context) == 3


def test_create_processing_task_has_four_context_tasks():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import (
        create_candidate_matching_agent,
        create_conversation_analyzer_agent,
        create_data_extractor_agent,
        create_job_description_analyzer_agent,
    )
    from tasks import (
        create_analysis_task,
        create_candidate_job_comparison_task,
        create_extraction_task,
        create_job_analysis_task,
        create_processing_task,
    )

    ext_agent = create_data_extractor_agent()
    ana_agent = create_conversation_analyzer_agent()
    job_agent = create_job_description_analyzer_agent()
    match_agent = create_candidate_matching_agent()

    proc_agent = create_data_extractor_agent()

    ext_task = create_extraction_task(ext_agent)
    ana_task = create_analysis_task(ana_agent, ext_task)
    job_task = create_job_analysis_task(job_agent, ext_task)
    comp_task = create_candidate_job_comparison_task(match_agent, ext_task, ana_task, job_task)
    proc_task = create_processing_task(proc_agent, ext_task, ana_task, job_task, comp_task)

    assert proc_task.agent is proc_agent
    assert ext_task in proc_task.context
    assert ana_task in proc_task.context
    assert job_task in proc_task.context
    assert comp_task in proc_task.context
    assert len(proc_task.context) == 4


def test_create_email_sending_task_depends_on_processing_task():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import (
        create_candidate_matching_agent,
        create_conversation_analyzer_agent,
        create_data_extractor_agent,
        create_job_description_analyzer_agent,
    )
    from tasks import (
        create_analysis_task,
        create_candidate_job_comparison_task,
        create_email_sending_task,
        create_extraction_task,
        create_job_analysis_task,
        create_processing_task,
    )

    ext_agent = create_data_extractor_agent()
    ana_agent = create_conversation_analyzer_agent()
    job_agent = create_job_description_analyzer_agent()
    match_agent = create_candidate_matching_agent()
    mail_agent = create_data_extractor_agent()

    ext_task = create_extraction_task(ext_agent)
    ana_task = create_analysis_task(ana_agent, ext_task)
    job_task = create_job_analysis_task(job_agent, ext_task)
    comp_task = create_candidate_job_comparison_task(match_agent, ext_task, ana_task, job_task)
    proc_task = create_processing_task(mail_agent, ext_task, ana_task, job_task, comp_task)
    email_task = create_email_sending_task(mail_agent, proc_task)

    assert email_task.agent is mail_agent
    assert proc_task in email_task.context
    assert len(email_task.context) == 1


def test_single_meet_tasks_chain_on_evaluator_agent():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_single_meet_evaluator_agent
    from tasks import create_single_meet_evaluation_task, create_single_meet_extraction_task

    meet_id = "550e8400-e29b-41d4-a716-446655440070"
    agent = create_single_meet_evaluator_agent()
    ext_task = create_single_meet_extraction_task(agent, meet_id)
    eval_task = create_single_meet_evaluation_task(agent, ext_task)

    assert ext_task.agent is agent
    assert eval_task.agent is agent
    assert ext_task in eval_task.context


def test_create_evaluation_saving_task_context_and_jd_hint():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import (
        create_candidate_matching_agent,
        create_conversation_analyzer_agent,
        create_data_extractor_agent,
        create_job_description_analyzer_agent,
    )
    from tasks import (
        create_analysis_task,
        create_candidate_job_comparison_task,
        create_evaluation_saving_task,
        create_extraction_task,
        create_job_analysis_task,
        create_processing_task,
    )

    ext_agent = create_data_extractor_agent()
    ana_agent = create_conversation_analyzer_agent()
    job_agent = create_job_description_analyzer_agent()
    match_agent = create_candidate_matching_agent()
    saver_agent = create_data_extractor_agent()

    ext_task = create_extraction_task(ext_agent)
    ana_task = create_analysis_task(ana_agent, ext_task)
    job_task = create_job_analysis_task(job_agent, ext_task)
    comp_task = create_candidate_job_comparison_task(match_agent, ext_task, ana_task, job_task)
    proc_task = create_processing_task(saver_agent, ext_task, ana_task, job_task, comp_task)

    jd_known = "550e8400-e29b-41d4-a716-446655440100"
    saving_with_jd = create_evaluation_saving_task(saver_agent, proc_task, jd_known)

    assert saving_with_jd.agent is saver_agent
    assert proc_task in saving_with_jd.context
    assert jd_known in saving_with_jd.description

    saving_find_jd = create_evaluation_saving_task(saver_agent, proc_task)

    assert proc_task in saving_find_jd.context
    assert "jd_interview_id" in saving_find_jd.description.lower()


def test_create_filtered_extraction_task_embeds_jd_id():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_data_extractor_agent
    from tasks import create_filtered_extraction_task

    jd_id = "550e8400-e29b-41d4-a716-446655440140"
    agent = create_data_extractor_agent()
    task = create_filtered_extraction_task(agent, jd_id)

    assert task.agent is agent
    assert jd_id in task.description
    assert "get_conversations_by_jd_interview" in task.description.lower()


def test_create_matching_task_recruiter_vs_global():
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_candidate_matching_agent
    from tasks import create_matching_task

    agent = create_candidate_matching_agent()
    uid = "550e8400-e29b-41d4-a716-446655440150"
    cid = "550e8400-e29b-41d4-a716-446655440151"

    t_rec = create_matching_task(agent, user_id=uid, client_id=cid)
    assert t_rec.agent is agent
    assert "get_candidates_by_recruiter" in t_rec.description
    assert uid in t_rec.description
    assert cid in t_rec.description
    assert "get_all_jd_interviews" in t_rec.description
    assert "get_existing_meets_candidates" in t_rec.description

    t_all = create_matching_task(agent)
    assert t_all.agent is agent
    assert "get_candidates_data()" in t_all.description
    assert "get_all_jd_interviews()" in t_all.description
    assert "get_existing_meets_candidates" in t_all.description


def test_create_single_meeting_minutes_task_context_and_save_tool():
    """879: minuta con contexto extraction + evaluation."""
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_single_meet_evaluator_agent
    from tasks import (
        create_single_meet_evaluation_task,
        create_single_meet_extraction_task,
        create_single_meeting_minutes_task,
    )

    meet_id = "550e8400-e29b-41d4-a716-446655440081"
    agent = create_single_meet_evaluator_agent()
    ext_task = create_single_meet_extraction_task(agent, meet_id)
    eval_task = create_single_meet_evaluation_task(agent, ext_task)
    minutes_task = create_single_meeting_minutes_task(agent, ext_task, eval_task)

    assert minutes_task.agent is agent
    assert ext_task in minutes_task.context
    assert eval_task in minutes_task.context
    assert "save_meeting_minute" in minutes_task.description.lower()


def test_create_elevenlabs_prompt_generation_task_embeds_strings():
    """953: Task con f-string de nombre, JD y email."""
    pytest.importorskip("crewai")
    pytest.importorskip("langchain_openai")

    from agents import create_elevenlabs_prompt_generator_agent
    from tasks import create_elevenlabs_prompt_generation_task

    agent = create_elevenlabs_prompt_generator_agent()
    name = "Búsqueda QA"
    jd = "Requiere Python y pytest."
    sender = "ops@cliente.example"

    task = create_elevenlabs_prompt_generation_task(agent, name, jd, sender)
    assert task.agent is agent
    assert name in task.description
    assert jd in task.description
    assert sender in task.description
