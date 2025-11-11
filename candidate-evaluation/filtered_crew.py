#!/usr/bin/env python3
"""
Crew para análisis filtrado por jd_interview_id
"""

from crewai import Crew, Process
from agents import create_filtered_data_extractor_agent, create_conversation_analyzer_agent, create_job_description_analyzer_agent, create_data_processor_agent, create_evaluation_saver_agent, create_email_sender_agent
from tasks import create_filtered_extraction_task, create_analysis_task, create_job_analysis_task, create_candidate_job_comparison_task, create_processing_task, create_evaluation_saving_task, create_email_sending_task

def create_filtered_data_processing_crew(jd_interview_id: str):
    """
    Crea el crew para análisis filtrado por jd_interview_id
    """
    
    # Crear agentes
    data_extractor = create_filtered_data_extractor_agent()
    conversation_analyzer = create_conversation_analyzer_agent()
    job_analyzer = create_job_description_analyzer_agent()
    data_processor = create_data_processor_agent()
    saver_agent = create_evaluation_saver_agent()
    email_sender = create_email_sender_agent()
    
    # Crear tareas
    extraction_task = create_filtered_extraction_task(data_extractor, jd_interview_id)
    analysis_task = create_analysis_task(conversation_analyzer, extraction_task)
    job_analysis_task = create_job_analysis_task(job_analyzer, extraction_task)
    comparison_task = create_candidate_job_comparison_task(data_processor, extraction_task, analysis_task, job_analysis_task)
    processing_task = create_processing_task(data_processor, extraction_task, analysis_task, job_analysis_task, comparison_task)
    saving_task = create_evaluation_saving_task(saver_agent, processing_task, jd_interview_id)
    email_task = create_email_sending_task(email_sender, processing_task)
    
    # Crear crew
    crew = Crew(
        agents=[data_extractor, conversation_analyzer, job_analyzer, data_processor, saver_agent, email_sender],
        tasks=[extraction_task, analysis_task, job_analysis_task, comparison_task, processing_task, saving_task, email_task],
        process=Process.sequential,
        verbose=False
    )
    
    return crew
