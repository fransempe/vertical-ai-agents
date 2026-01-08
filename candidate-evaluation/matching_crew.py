#!/usr/bin/env python3
"""
Crew para matching de candidatos con entrevistas
"""

from crewai import Crew, Process
from agents import create_candidate_matching_agent
from tasks import create_matching_task

def create_candidate_matching_crew(user_id: str = None, client_id: str = None):
    """
    Crea el crew para matching de candidatos con entrevistas
    
    Args:
        user_id: ID del usuario para filtrar candidatos (opcional)
        client_id: ID del cliente para filtrar candidatos (opcional)
    """
    
    # Crear agente de matching
    matching_agent = create_candidate_matching_agent(user_id=user_id, client_id=client_id)
    
    # Crear tarea de matching
    matching_task = create_matching_task(matching_agent, user_id=user_id, client_id=client_id)
    
    # Crear crew
    crew = Crew(
        agents=[matching_agent],
        tasks=[matching_task],
        process=Process.sequential,
        verbose=True
    )
    
    return crew
