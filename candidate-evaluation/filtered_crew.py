#!/usr/bin/env python3
"""
Crew para análisis filtrado por jd_interview_id
"""

from crewai import Crew, Process
from agents import create_filtered_data_extractor_agent, create_conversation_analyzer_agent, create_job_description_analyzer_agent, create_data_processor_agent, create_evaluation_saver_agent, create_email_sender_agent
from tasks import create_filtered_extraction_task, create_analysis_task, create_job_analysis_task, create_candidate_job_comparison_task, create_processing_task, create_evaluation_saving_task, create_email_sending_task
from tools.supabase_tools import get_conversations_by_jd_interview

def create_filtered_data_processing_crew(jd_interview_id: str):
    """
    Crea el crew para análisis filtrado por jd_interview_id
    """
    try:
        # Intentar diferentes formas de acceder a la función original del Tool
        func_to_call = None
        if hasattr(get_conversations_by_jd_interview, '__wrapped__'):
            func_to_call = get_conversations_by_jd_interview.__wrapped__
        elif hasattr(get_conversations_by_jd_interview, 'func'):
            func_to_call = get_conversations_by_jd_interview.func
        elif hasattr(get_conversations_by_jd_interview, '_func'):
            func_to_call = get_conversations_by_jd_interview._func
        elif callable(get_conversations_by_jd_interview) and not hasattr(get_conversations_by_jd_interview, 'name'):
            # Si es directamente callable y no tiene atributos de Tool
            func_to_call = get_conversations_by_jd_interview
        
        if func_to_call:
            data = func_to_call(jd_interview_id)
            print("data: ", data)
        else:
            print("No se pudo acceder a la función subyacente del Tool")
    except Exception as e:
        print(f"Error al probar get_conversations_by_jd_interview: {str(e)}")
        import traceback
        print(traceback.format_exc())
    
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
