# crew.py
from crewai import Crew, Process
from agents import (
    create_data_extractor_agent,
    create_conversation_analyzer_agent, 
    create_data_processor_agent
)
from tasks import (
    create_extraction_task,
    create_analysis_task,
    create_processing_task
)

def create_data_processing_crew():
    """Crea el crew completo para procesamiento de datos"""
    
    # Crear agentes
    extractor_agent = create_data_extractor_agent()
    analyzer_agent = create_conversation_analyzer_agent()
    processor_agent = create_data_processor_agent()
    
    # Crear tareas
    extraction_task = create_extraction_task(extractor_agent)
    analysis_task = create_analysis_task(analyzer_agent, extraction_task)
    processing_task = create_processing_task(processor_agent, extraction_task, analysis_task)
    
    # Crear crew
    crew = Crew(
        agents=[extractor_agent, analyzer_agent, processor_agent], # analyzer_agent, processor_agent
        tasks=[extraction_task, analysis_task, processing_task], # analysis_task, processing_task
        process=Process.sequential,
        verbose=True
    )
    
    return crew
