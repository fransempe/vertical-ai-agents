# crew.py
from crewai import Crew, Process
from agents import (
    create_data_extractor_agent,
    create_conversation_analyzer_agent,
    create_job_description_analyzer_agent,
    create_data_processor_agent,
    create_evaluation_saver_agent,
    create_email_sender_agent
)
from tasks import (
    create_extraction_task,
    create_analysis_task,
    create_job_analysis_task,
    create_candidate_job_comparison_task,
    create_processing_task,
    create_evaluation_saving_task,
    create_email_sending_task
)

def create_data_processing_crew():
    """Crea el crew completo para procesamiento de datos con análisis de job descriptions y envío de email"""
    
    # Crear agentes
    extractor_agent = create_data_extractor_agent()
    analyzer_agent = create_conversation_analyzer_agent()
    job_analyzer_agent = create_job_description_analyzer_agent()
    processor_agent = create_data_processor_agent()
    saver_agent = create_evaluation_saver_agent()
    email_agent = create_email_sender_agent()
    
    # Crear tareas
    extraction_task = create_extraction_task(extractor_agent)
    analysis_task = create_analysis_task(analyzer_agent, extraction_task)
    job_analysis_task = create_job_analysis_task(job_analyzer_agent, extraction_task)
    comparison_task = create_candidate_job_comparison_task(job_analyzer_agent, extraction_task, analysis_task, job_analysis_task)
    processing_task = create_processing_task(processor_agent, extraction_task, analysis_task, job_analysis_task, comparison_task)
    saving_task = create_evaluation_saving_task(saver_agent, processing_task)
    email_task = create_email_sending_task(email_agent, processing_task)
    
    # Crear crew
    crew = Crew(
        agents=[extractor_agent, analyzer_agent, job_analyzer_agent, processor_agent, saver_agent, email_agent],
        tasks=[extraction_task, analysis_task, job_analysis_task, comparison_task, processing_task, saving_task, email_task],
        process=Process.sequential,
        verbose=True
    )
    
    return crew
