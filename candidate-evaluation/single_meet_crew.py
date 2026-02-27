#!/usr/bin/env python3
"""
Crew para evaluar un solo meet
"""

from crewai import Crew, Process
from agents import create_single_meet_evaluator_agent  # , create_meeting_minutes_agent  # COMENTADO: meeting_minutes_knowledge
from tasks import (
    create_single_meet_extraction_task,
    create_single_meet_evaluation_task,
    # create_single_meeting_minutes_task,  # COMENTADO: meeting_minutes_knowledge
)
from tools.supabase_tools import get_meet_evaluation_data

def create_single_meet_evaluation_crew(meet_id: str):
    """
    Crea el crew para evaluar un solo meet
    
    Args:
        meet_id: ID del meet a evaluar
    """
    try:
        # Intentar diferentes formas de acceder a la función original del Tool
        func_to_call = None
        if hasattr(get_meet_evaluation_data, '__wrapped__'):
            func_to_call = get_meet_evaluation_data.__wrapped__
        elif hasattr(get_meet_evaluation_data, 'func'):
            func_to_call = get_meet_evaluation_data.func
        elif hasattr(get_meet_evaluation_data, '_func'):
            func_to_call = get_meet_evaluation_data._func
        elif callable(get_meet_evaluation_data) and not hasattr(get_meet_evaluation_data, 'name'):
            # Si es directamente callable y no tiene atributos de Tool
            func_to_call = get_meet_evaluation_data
        
        if func_to_call:
            data = func_to_call(meet_id)
        else:
            print("No se pudo acceder a la función subyacente del Tool")
    except Exception as e:
        print(f"Error al probar get_meet_evaluation_data: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
    # Crear agentes
    evaluator = create_single_meet_evaluator_agent()
    # minutes_agent = create_meeting_minutes_agent()  # COMENTADO: meeting_minutes_knowledge

    # Crear tareas
    extraction_task = create_single_meet_extraction_task(evaluator, meet_id)
    evaluation_task = create_single_meet_evaluation_task(evaluator, extraction_task)
    # minutes_task = create_single_meeting_minutes_task(minutes_agent, extraction_task, evaluation_task)  # COMENTADO: meeting_minutes_knowledge

    # Crear crew: primero extrae, luego evalúa
    # COMENTADO: meeting_minutes_knowledge - ya no se genera/guarda la minuta
    crew = Crew(
        agents=[evaluator],  # , minutes_agent],  # COMENTADO: meeting_minutes_knowledge
        tasks=[extraction_task, evaluation_task],  # , minutes_task],  # COMENTADO: meeting_minutes_knowledge
        process=Process.sequential,
        verbose=True
    )
    
    return crew

