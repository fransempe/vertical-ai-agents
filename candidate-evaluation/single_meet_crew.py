#!/usr/bin/env python3
"""
Crew para evaluar un solo meet
"""

from crewai import Crew, Process
from agents import create_single_meet_evaluator_agent
from tasks import create_single_meet_extraction_task, create_single_meet_evaluation_task

def create_single_meet_evaluation_crew(meet_id: str):
    """
    Crea el crew para evaluar un solo meet
    
    Args:
        meet_id: ID del meet a evaluar
    """
    
    # Crear agente
    evaluator = create_single_meet_evaluator_agent()
    
    # Crear tareas
    extraction_task = create_single_meet_extraction_task(evaluator, meet_id)
    evaluation_task = create_single_meet_evaluation_task(evaluator, extraction_task)
    
    # Crear crew
    crew = Crew(
        agents=[evaluator],
        tasks=[extraction_task, evaluation_task],
        process=Process.sequential,
        verbose=True
    )
    
    return crew

