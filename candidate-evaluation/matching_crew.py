#!/usr/bin/env python3
"""
Crew para matching de candidatos con entrevistas
"""

from crewai import Crew, Process
from agents import create_candidate_matching_agent
from tasks import create_matching_task

def create_candidate_matching_crew():
    """
    Crea el crew para matching de candidatos con entrevistas
    """
    
    # Crear agente de matching
    matching_agent = create_candidate_matching_agent()
    
    # Crear tarea de matching
    matching_task = create_matching_task(matching_agent)
    
    # Crear crew
    crew = Crew(
        agents=[matching_agent],
        tasks=[matching_task],
        process=Process.sequential,
        verbose=True
    )
    
    return crew
